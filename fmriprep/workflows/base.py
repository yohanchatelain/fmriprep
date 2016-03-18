#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Created on Wed Dec  2 17:35:40 2015

@author: craigmoodie
"""

import os
import os.path as op
import pkg_resources as pkgr

from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from nipype.interfaces.fsl import (Merge, MCFLIRT, BET, FAST, FLIRT, TOPUP, FUGUE, BinaryMaths,
                                   UnaryMaths, ApplyWarp, ConvertXFM, ConvertWarp, Split, MeanImage)
from nipype.interfaces.ants import N4BiasFieldCorrection, Registration, ApplyTransforms, BrainExtraction

from fmriprep.workflows.anatomical import t1w_preprocessing
from fmriprep.variables_preprocessing import data_dir, work_dir, plugin, plugin_args

def fmri_preprocess(name='fMRI_prep', settings=None, subject_list=None):
    """
    The main fmri preprocessing workflow.
    """

    if settings is None:
        settings = {}

    for key in ['fsl', 'skull_strip', 'epi', 'connectivity']:
        if settings.get(key) is None:
            settings[key] = {}

    dwell_time = settings['epi'].get('dwell_time', 0.000700012460221792)

    if subject_list is None or not subject_list:
        raise RuntimeError('No subjects were specified')

    t1w_preproc = t1w_preprocessing(settings=settings)
    
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['fieldmaps', 'fieldmaps_meta', 'epi', 'epi_meta', 'sbref', 'sbref_meta', 't1']),
        name='inputnode')

    fslmerge = pe.Node(Merge(dimension='t'), name="Merge_Fieldmaps")
    motion_correct_SE_maps = pe.Node(MCFLIRT(), name="Motion_Correction")

    # Skull strip EPI  (try ComputeMask(BaseInterface))
    EPI_BET = pe.Node(
        BET(mask=True, functional=True, frac=0.6), name="EPI_BET")

    # Skull strip SBRef to get reference brain
    SBRef_BET = pe.Node(
        BET(mask=True, functional=True, frac=0.6), name="SBRef_BET")

    # Skull strip the SBRef with ANTS Brain Extraction

    #from nipype.interfaces.ants.segmentation import BrainExtraction
    #SBRef_skull_strip = pe.Node(BrainExtraction(), name = "antsreg_T1_Brain_Extraction")
    #SBRef_skull_strip.inputs.dimension = 3
    #SBRef_skull_strip.inputs.brain_template = "/home/cmoodie/Oasis_MICCAI2012-Multi-Atlas-Challenge-Data/T_template0.nii.gz"
    #SBRef_skull_strip.inputs.brain_probability_mask = "/home/cmoodie/Oasis_MICCAI2012-Multi-Atlas-Challenge-Data/T_template0_BrainCerebellumProbabilityMask.nii.gz"
    #SBRef_skull_strip.inputs.extraction_registration_mask = "/home/cmoodie/Oasis_MICCAI2012-Multi-Atlas-Challenge-Data/T_template0_BrainCerebellumRegistrationMask.nii.gz"


    # Affine transform of T1 segmentation into SBRref space
    flt_wmseg_sbref = pe.Node(FLIRT(dof=6, bins=640, cost_func='mutualinfo'),
                              name="WMSeg_2_SBRef_Brain_Affine_Transform")

    # Topup Steps
    create_parameters_node = pe.Node(niu.Function(
        input_names=["fieldmaps", "fieldmaps_meta"], output_names=["parameters_file"],
        function=create_encoding_file), name="Create_Parameters", updatehash=True)

    # Run topup to estimate filed distortions
    topup = pe.Node(TOPUP(), name="TopUp")

    # Distortion Correction using the TopUp Fi

    # Convert topup fieldmap to rad/s [ 1 Hz = 6.283 rad/s]
    fmap_scale = pe.Node(BinaryMaths(operation='mul', operand_value=6.283),
                         name="Scale_Fieldmap")

    # Skull strip SE Fieldmap magnitude image to get reference brain and mask
    fmap_mag_BET = pe.Node(BET(mask=True, robust=True), name="Fmap_Mag_BET")
    # Might want to turn off bias reduction if it is being done in a separate node!
    #fmap_mag_BET.inputs.reduce_bias = True

    # Unwarp SBRef using Fugue  (N.B. duplicated in epi_reg_workflow!!!!!)
    fugue_sbref = pe.Node(FUGUE(unwarp_direction='x', dwell_time=dwell_time),
                          name="SBRef_Unwarping")

    strip_corrected_sbref = pe.Node(BET(mask=True, frac=0.6, robust=True),
                                    name="BET_Corrected_SBRef")

    # Run MCFLIRT to get motion matrices
    # Motion Correction of the EPI with SBRef as Target
    motion_correct_epi = pe.Node(
        MCFLIRT(save_mats=True), name="Motion_Correction_EPI")

    ################################ Run the commands from epi_reg_dof #######
    # do a standard flirt pre-alignment
    # flirt -ref ${vrefbrain} -in ${vepi} -dof ${dof} -omat ${vout}_init.mat
    flt_epi_sbref = pe.Node(FLIRT(
        dof=6, bins=640, cost_func='mutualinfo'), name="EPI_2_SBRef_Brain_Affine_Transform")

    # WITH FIELDMAP (unwarping steps)
    # flirt -in ${fmapmagbrain} -ref ${vrefbrain} -dof ${dof} -omat ${vout}_fieldmap2str_init.mat
    flt_fmap_mag_brain_sbref_brain = pe.Node(FLIRT(dof=6, bins=640, cost_func='mutualinfo'),
                                             name="Fmap_Mag_Brain_2_SBRef_Brain_Affine_Transform")

    # flirt -in ${fmapmaghead} -ref ${vrefhead} -dof ${dof} -init ${vout}_fieldmap2str_init.mat -omat ${vout}_fieldmap2str.mat -out ${vout}_fieldmap2str -nosearch
    flt_fmap_mag_sbref = pe.Node(FLIRT(dof=6, no_search=True, bins=640, cost_func='mutualinfo'),
                                 name="Fmap_Mag_2_SBRef_Affine_Transform")

    # unmask the fieldmap (necessary to avoid edge effects)
    # fslmaths ${fmapmagbrain} -abs -bin ${vout}_fieldmaprads_mask
    fmapmagbrain_abs = pe.Node(
        UnaryMaths(operation='abs'), name="Abs_Fieldmap_Mag_Brain")
    fmapmagbrain_bin = pe.Node(
        UnaryMaths(operation='bin'), name="Binarize_Fieldmap_Mag_Brain")

    # fslmaths ${fmaprads} -abs -bin -mul ${vout}_fieldmaprads_mask ${vout}_fieldmaprads_mask
    fmap_abs = pe.Node(UnaryMaths(operation='abs'), name="Abs_Fieldmap")
    fmap_bin = pe.Node(UnaryMaths(operation='bin'), name="Binarize_Fieldmap")
    fmap_mul = pe.Node(
        BinaryMaths(operation='mul'), name="Fmap_Multiplied_by_Mask")

    # fugue --loadfmap=${fmaprads} --mask=${vout}_fieldmaprads_mask --unmaskfmap --savefmap=${vout}_fieldmaprads_unmasked --unwarpdir=${fdir}   # the direction here should take into account the initial affine (it needs to be the direction in the EPI)
    fugue_unmask = pe.Node(FUGUE(unwarp_direction='x', dwell_time=dwell_time,
                                 save_unmasked_fmap=True), name="Fmap_Unmasking")

    # the following is a NEW HACK to fix extrapolation when fieldmap is too small
    # applywarp -i ${vout}_fieldmaprads_unmasked -r ${vrefhead} --premat=${vout}_fieldmap2str.mat -o ${vout}_fieldmaprads2str_pad0
    aw_fmap_unmasked_sbref = pe.Node(
        ApplyWarp(relwarp=True), name="Apply_Warp_Fmap_Unmasked_2_SBRef")

    # fslmaths ${vout}_fieldmaprads2str_pad0 -abs -bin ${vout}_fieldmaprads2str_innermask
    fmap_unmasked_abs = pe.Node(
        UnaryMaths(operation='abs'), name="Abs_Fmap_Unmasked_Warp")
    fmap_unmasked_bin = pe.Node(
        UnaryMaths(operation='bin'), name="Binarize_Fmap_Unmasked_Warp")

    # fugue --loadfmap=${vout}_fieldmaprads2str_pad0 --mask=${vout}_fieldmaprads2str_innermask --unmaskfmap --unwarpdir=${fdir} --savefmap=${vout}_fieldmaprads2str_dilated
    fugue_dilate = pe.Node(FUGUE(unwarp_direction='x', dwell_time=dwell_time,
                                 save_unmasked_fmap=True), name="Fmap_Dilating")

    # fslmaths ${vout}_fieldmaprads2str_dilated ${vout}_fieldmaprads2str
    # !!!! Don't need to do this since this just does the same thing as a "mv" command. Just connect previous fugue node directly to subsequent flirt command.
    # run bbr to SBRef target with fieldmap and T1 seg in SBRef space
    # flirt -ref ${vrefhead} -in ${vepi} -dof ${dof} -cost bbr -wmseg ${vout}_fast_wmseg -init ${vout}_init.mat -omat ${vout}.mat -out ${vout}_1vol -schedule ${FSLDIR}/etc/flirtsch/bbr.sch -echospacing ${dwell} -pedir ${pe_dir} -fieldmap ${vout}_fieldmaprads2str $wopt
    flt_bbr = pe.Node(FLIRT(dof=6, bins=640, cost_func='bbr', pedir=1, echospacing=dwell_time),
                      name="Flirt_BBR")
    flt_bbr.inputs.schedule = settings['fsl'].get(
        'flirt_bbr', op.join(os.getenv('FSLDIR'), 'etc/flirtsch/bbr.sch'))

    # make equivalent warp fields
    # convert_xfm -omat ${vout}_inv.mat -inverse ${vout}.mat
    invt_bbr = pe.Node(
        ConvertXFM(invert_xfm=True), name="BBR_Inverse_Transform")

    # convert_xfm -omat ${vout}_fieldmaprads2epi.mat -concat ${vout}_inv.mat ${vout}_fieldmap2str.mat
    concat_mats = pe.Node(ConvertXFM(concat_xfm=True), name="BBR_Concat")

    # applywarp -i ${vout}_fieldmaprads_unmasked -r ${vepi} --premat=${vout}_fieldmaprads2epi.mat -o ${vout}_fieldmaprads2epi
    aw_fmap_unmasked_epi = pe.Node(
        ApplyWarp(relwarp=True), name="Apply_Warp_Fmap_Unmasked_2_EPI")

    # fslmaths ${vout}_fieldmaprads2epi -abs -bin ${vout}_fieldmaprads2epi_mask
    fieldmaprads2epi_abs = pe.Node(
        UnaryMaths(operation='abs'), name="Abs_Fmap_2_EPI_Unmasked_Warp")
    fieldmaprads2epi_bin = pe.Node(
        UnaryMaths(operation='bin'), name="Binarize_Fmap_2_EPI_Unmasked_Warp")

    # fugue --loadfmap=${vout}_fieldmaprads2epi --mask=${vout}_fieldmaprads2epi_mask --saveshift=${vout}_fieldmaprads2epi_shift --unmaskshift --dwell=${dwell} --unwarpdir=${fdir}
    fugue_shift = pe.Node(FUGUE(unwarp_direction='x', dwell_time=dwell_time,
                                save_unmasked_shift=True), name="Fmap_Shift")

    # convertwarp -r ${vrefhead} -s ${vout}_fieldmaprads2epi_shift --postmat=${vout}.mat -o ${vout}_warp --shiftdir=${fdir} --relout
    convert_fmap_shift = pe.MapNode(
        ConvertWarp(out_relwarp=True, shift_direction='x'), name="Convert_Fieldmap_Shift", iterfield=["premat"])

    split_epi = pe.Node(Split(dimension='t'), "Split_EPI")

    # applywarp -i ${vepi} -r ${vrefhead} -o ${vout} -w ${vout}_warp --interp=spline --rel
    aw_final = pe.MapNode(
        ApplyWarp(relwarp=True), name="Apply_Final_Warp", iterfield=["field_file", "in_file"])

    merge_epi = pe.Node(Merge(dimension='t'), "Merge_EPI")

    # BBR of Unwarped and SBRef-Reg
    epi_mean = pe.Node(MeanImage(dimension='T'), name="EPI_mean_volume")

    # epi_reg --epi=sub-S2529LVY1263171_task-nback_run-1_bold_brain
    # --t1=../Preprocessing_test_workflow/_subject_id_S2529LVY1263171/Bias_Field_Correction/sub-S2529LVY1263171_run-1_T1w_corrected.nii.gz
    # --t1brain=sub-S2529LVY1263171_run-1_T1w_corrected_bet_brain.nii.gz
    # --out=sub-S2529LVY1263171/func/sub-S2529LVY1263171_task-nback_run-1_bold_undistorted
    # --fmap=Topup_Fieldmap_rad.nii.gz
    # --fmapmag=fieldmap_topup_corrected.nii.gz
    # --fmapmagbrain=Magnitude_brain.nii.gz --echospacing=dwell_time
    # --pedir=x- -v

    flt_sbref_brain_t1_brain = pe.Node(FLIRT(
        dof=6, bins=640, cost_func='mutualinfo'), name="SBRef_Brain_2_T1_Brain_Affine_Transform")
    flt_sbref_2_T1 = pe.Node(
        FLIRT(dof=6, bins=640, cost_func='mutualinfo'), name="SBRef_2_T1_Affine_Transform")
    bbr_sbref_2_T1 = pe.Node(
        FLIRT(dof=6, pedir=1, echospacing=dwell_time, bins=640, cost_func='bbr'), name="BBR_SBRef_to_T1")
    bbr_sbref_2_T1.inputs.schedule = settings['fsl'].get(
        'flirt_bbr', op.join(os.getenv('FSLDIR'), 'etc/flirtsch/bbr.sch'))

    invt_mat = pe.Node(
        ConvertXFM(invert_xfm=True), name="EpiReg_Inverse_Transform")

    flt_parcels_2_sbref = pe.Node(FLIRT(
        dof=12, bins=640, cost_func='mutualinfo', interp='nearestneighbour'),
                                  name="Parcels_2_EPI_Mean_Affine_w_Inv_Mat")

    ########################################## Connecting Workflow pe.Nodes ##

    workflow.connect([ 
        (t1w_preproc, flt_wmseg_sbref, [('T1_Segmentation.tissue_class_files', 'in_file')]),
    ])
    '''
        (inputnode, fslmerge, [('fieldmaps', 'in_files')]),
        (fslmerge, motion_correct_SE_maps, [('merged_file', 'in_file')]),
        (inputnode, motion_correct_SE_maps, [('sbref', 'ref_file')]),
        (inputnode, EPI_BET, [('epi', 'in_file')]),
        (inputnode, SBRef_BET, [('sbref', 'in_file')]),
        #(inputnode, n4, [('t1', 'input_image')]),
        #(n4, T1_skull_strip, [('output_image', 'anatomical_image')]),
        #(n4, T1_seg, [('output_image', 'in_files')]),
        #(n4, antsreg, [('output_image', 'moving_image')]),
        #(antsreg, at, [('inverse_composite_transform', 'transforms')]),
        (t1w_preprocessing_workflow, flt_wmseg_sbref, [('tissue_class_map', 'in_file')]),
        (t1w_preprocessing_workflow, bbr_sbref_2_T1, [('tissue_class_map', 'wm_seg')]),
        (t1w_preprocessing_workflow, flt_parcels_2_sbref, [('output_image', 'in_file')]),
        (t1w_preprocessing_workflow, flt_sbref_brain_t1_brain, [('BrainExtractionBrain', 'reference')]),
        (t1w_preprocessing_workflow, flt_sbref_2_T1, [('output_image', 'reference')]),
        (t1w_preprocessing_workflow, bbr_sbref_2_T1, [('output_image', 'reference')]),
        (inputnode, flt_wmseg_sbref, [('sbref', 'reference')]),
        #(inputnode, SBRef_skull_strip, [("sbref", "in_file")]),
        (inputnode, create_parameters_node, [('fieldmaps', 'fieldmaps')]),
        (inputnode, create_parameters_node, [('fieldmaps_meta', 'fieldmaps_meta')]),
        (create_parameters_node, topup, [('parameters_file', 'encoding_file')]),
        (motion_correct_SE_maps, topup, [('out_file', 'in_file')]),
        (topup, fmap_scale, [('out_field', 'in_file')]),
        (topup, fmap_mag_BET, [('out_corrected', 'in_file')]),
        (fmap_scale, fugue_sbref, [('out_file', 'fmap_in_file')]),
        (fmap_mag_BET, fugue_sbref, [('mask_file', 'mask_file')]),
        (inputnode, fugue_sbref, [('sbref', 'in_file')]),
        (fugue_sbref, strip_corrected_sbref, [('unwarped_file', 'in_file')]),
        (EPI_BET, motion_correct_epi, [('out_file', 'in_file')]),
        (inputnode, motion_correct_epi, [('sbref', 'ref_file')]),
        (EPI_BET, flt_epi_sbref, [('out_file', 'in_file')]),
        # might need to switch to [strip_corrected_sbref, "in_file"] here
        # instead of [SBRef_BET, "out_file"]
        (SBRef_BET, flt_epi_sbref, [('out_file', 'reference')]),
        (fmap_mag_BET, flt_fmap_mag_brain_sbref_brain, [('out_file', 'in_file')]),
        # might need to switch to [strip_corrected_sbref, "in_file"] here
        # instead of [SBRef_BET, "out_file"]
        (SBRef_BET, flt_fmap_mag_brain_sbref_brain, [('out_file', 'reference')]),
        (topup, flt_fmap_mag_sbref, [('out_corrected', 'in_file')]),
        (fugue_sbref, flt_fmap_mag_sbref, [('unwarped_file', 'reference')]),
        (flt_fmap_mag_brain_sbref_brain, flt_fmap_mag_sbref, [
            ('out_matrix_file', 'in_matrix_file')]),
        (topup, fmapmagbrain_abs, [('out_corrected', 'in_file')]),
        (fmapmagbrain_abs, fmapmagbrain_bin, [('out_file', 'in_file')]),
        (fmap_scale, fmap_abs, [('out_file', 'in_file')]),
        (fmap_abs, fmap_bin, [('out_file', 'in_file')]),
        (fmap_bin, fmap_mul, [('out_file', 'in_file')]),
        (fmapmagbrain_bin, fmap_mul, [('out_file', 'operand_file')]),
        (fmap_scale, fugue_unmask, [('out_file', 'fmap_in_file')]),
        (fmap_mul, fugue_unmask, [('out_file', 'mask_file')]),
        (fugue_unmask, aw_fmap_unmasked_sbref, [('fmap_out_file', 'in_file')]),
        (flt_fmap_mag_sbref, aw_fmap_unmasked_sbref, [('out_matrix_file', 'premat')]),
        (fugue_sbref, aw_fmap_unmasked_sbref, [('unwarped_file', 'ref_file')]),
        (aw_fmap_unmasked_sbref, fmap_unmasked_abs, [('out_file', 'in_file')]),
        (fmap_unmasked_abs, fmap_unmasked_bin, [('out_file', 'in_file')]),
        (aw_fmap_unmasked_sbref, fugue_dilate, [('out_file', 'fmap_in_file')]),
        (fmap_unmasked_bin, fugue_dilate, [('out_file', 'mask_file')]),
        (EPI_BET, flt_bbr, [('out_file', 'in_file')]),
        (fugue_sbref, flt_bbr, [('unwarped_file', 'reference')]),
        (fugue_dilate, flt_bbr, [('fmap_out_file', 'fieldmap')]),
        (flt_epi_sbref, flt_bbr, [('out_matrix_file', 'in_matrix_file')]),
        (flt_wmseg_sbref, flt_bbr, [('out_file', 'wm_seg')]),
        (flt_bbr, invt_bbr, [('out_matrix_file', 'in_file')]),
        (flt_fmap_mag_sbref, concat_mats, [('out_matrix_file', 'in_file')]),
        (invt_bbr, concat_mats, [('out_file', 'in_file2')]),
        (fugue_unmask, aw_fmap_unmasked_epi, [('fmap_out_file', 'in_file')]),
        (EPI_BET, aw_fmap_unmasked_epi, [('out_file', 'ref_file')]),
        (concat_mats, aw_fmap_unmasked_epi, [('out_file', 'premat')]),
        (aw_fmap_unmasked_epi, fieldmaprads2epi_abs, [('out_file', 'in_file')]),
        (fieldmaprads2epi_abs, fieldmaprads2epi_bin, [('out_file', 'in_file')]),
        (aw_fmap_unmasked_epi, fugue_shift, [('out_file', 'fmap_in_file')]),
        (fieldmaprads2epi_bin, fugue_shift, [('out_file', 'mask_file')]),
        (fugue_sbref, convert_fmap_shift, [('unwarped_file', 'reference')]),
        (fugue_shift, convert_fmap_shift, [('shift_out_file', 'shift_in_file')]),
        (flt_bbr, convert_fmap_shift, [('out_matrix_file', 'postmat')]),
        (motion_correct_epi, convert_fmap_shift, [('mat_file', 'premat')]),
        (inputnode, split_epi, [('epi', 'in_file')]),
        (split_epi, aw_final, [('out_files', 'in_file')]),
        (fugue_sbref, aw_final, [('unwarped_file', 'ref_file')]),
        (convert_fmap_shift, aw_final, [('out_file', 'field_file')]),
        (aw_final, merge_epi, [('out_file', 'in_files')]),
        (merge_epi, epi_mean, [('merged_file', 'in_file')]),
        (strip_corrected_sbref, flt_sbref_brain_t1_brain, [('out_file', 'in_file')]),
        (fugue_sbref, flt_sbref_2_T1, [('unwarped_file', 'in_file')]),
        (flt_sbref_brain_t1_brain, flt_sbref_2_T1, [('out_matrix_file', 'in_matrix_file')]),
        (strip_corrected_sbref, bbr_sbref_2_T1, [('out_file', 'in_file')]),
        (fugue_dilate, bbr_sbref_2_T1, [('fmap_out_file', 'fieldmap')]),
        (flt_sbref_2_T1, bbr_sbref_2_T1, [('out_matrix_file', 'in_matrix_file')]),
        (bbr_sbref_2_T1, invt_mat, [('out_matrix_file', 'in_file')]),
        (invt_mat, flt_parcels_2_sbref, [('out_file', 'in_matrix_file')]),
        (fugue_sbref, flt_parcels_2_sbref, [('unwarped_file', 'reference')])
    '''

    return workflow


def create_encoding_file(fieldmaps, fieldmaps_meta):
    """Creates a valid encoding file for topup"""
    import os
    import json
    import nibabel as nb
    with open("parameters.txt", "w") as parameters_file:
        for fieldmap, fieldmap_meta in zip(fieldmaps, fieldmaps_meta):
            meta = json.load(open(fieldmap_meta))
            pedir = {'x': 0, 'y': 1, 'z': 2}
            line_values = [0, 0, 0, meta["TotalReadoutTime"]]
            line_values[pedir[meta["PhaseEncodingDirection"][0]]
                        ] = 1 + (-2*(len(meta["PhaseEncodingDirection"]) == 2))
            for i in range(nb.load(fieldmap).shape[-1]):
                parameters_file.write(
                    " ".join([str(i) for i in line_values]) + "\n")
    return os.path.abspath("parameters.txt")
