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

from .anatomical import t1w_preprocessing
from .fieldmap import se_pair_workflow
from .epi import sbref_workflow
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

    
    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(niu.IdentityInterface(
        fields=['fieldmaps', 'fieldmaps_meta', 'epi', 'epi_meta', 'sbref', 'sbref_meta', 't1']),
        name='inputnode')

    t1w_preproc = t1w_preprocessing(settings=settings)
    sepair_wf = se_pair_workflow(settings=settings)
    sbref_wf = sbref_workflow(settings=settings)

    # Skull strip EPI  (try ComputeMask(BaseInterface))
    EPI_BET = pe.Node(
        BET(mask=True, functional=True, frac=0.6), name="EPI_BET")



    # Topup Steps
    create_parameters_node = pe.Node(niu.Function(
        input_names=["fieldmaps", "fieldmaps_meta"], output_names=["parameters_file"],
        function=create_encoding_file), name="Create_Parameters", updatehash=True)


    # Distortion Correction using the TopUp Fi


    # Run MCFLIRT to get motion matrices
    # Motion Correction of the EPI with SBRef as Target
    motion_correct_epi = pe.Node(
        MCFLIRT(save_mats=True), name="Motion_Correction_EPI")

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
        (inputnode, t1w_preproc, [('t1', 'inputnode.t1')]),
        (inputnode, sepair_wf, [('fieldmaps', 'inputnode.fieldmaps'),
                                ('sbref', 'inputnode.sbref')]),
        (inputnode, sbref_wf, [('sbref', 'inputnode.sbref')]),

        (inputnode, EPI_BET, [('epi', 'in_file')]),
        (inputnode, t1w_preproc, [('t1', 'inputnode.t1')]),
        (t1w_preproc, flt_wmseg_sbref, [('T1_Segmentation.tissue_class_map', 'in_file')]),
        (t1w_preproc, bbr_sbref_2_T1, [('T1_Segmentation.tissue_class_map', 'wm_seg')]),
        (t1w_preproc, flt_parcels_2_sbref, [('Bias_Field_Correction.output_image', 'in_file')]),
        (t1w_preproc, flt_sbref_brain_t1_brain, [('antsreg_T1_Brain_Extraction.BrainExtractionBrain', 'reference')]),
        (t1w_preproc, flt_sbref_2_T1, [('Bias_Field_Correction.output_image', 'reference')]),
        (t1w_preproc, bbr_sbref_2_T1, [('Bias_Field_Correction.output_image', 'reference')]),
        #(inputnode, SBRef_skull_strip, [("sbref", "in_file")]),
        (inputnode, create_parameters_node, [('fieldmaps', 'fieldmaps')]),
        (inputnode, create_parameters_node, [('fieldmaps_meta', 'fieldmaps_meta')]),
        (sepair_wf, sbref_wf, [('outputnode.fmap_scaled', 'inputnode.fmap_scaled')]),
        (sepair_wf, sbref_wf, [('outputnode.mag_brain', 'inputnode.mag_brain')]),
        (sepair_wf, sbref_wf, [('outputnode.fmap_mask', 'inputnode.fmap_mask')]),
        (sepair_wf, sbref_wf, [('outputnode.out_topup', 'inputnode.in_topup')]),        
        (sepair_wf, sbref_wf, [('outputnode.fmap_unmasked', 'inputnode.fmap_unmasked')]),
        (EPI_BET, motion_correct_epi, [('out_file', 'in_file')]),
        (inputnode, motion_correct_epi, [('sbref', 'ref_file')]),
        (EPI_BET, flt_epi_sbref, [('out_file', 'in_file')]),
        (EPI_BET, flt_bbr, [('out_file', 'in_file')]),
        (sbref_wf, flt_bbr, [('outputnode.sbref_unwarped', 'reference')]),
        (sbref_wf, flt_bbr, [('outputnode.sbref_fmap', 'fieldmap')]),
        (flt_epi_sbref, flt_bbr, [('out_matrix_file', 'in_matrix_file')]),
        (flt_wmseg_sbref, flt_bbr, [('out_file', 'wm_seg')]),
        (flt_bbr, invt_bbr, [('out_matrix_file', 'in_file')]),
        (sbref_wf, concat_mats, [('outputnode.mag2sbref_matrix', 'in_file')]),
        (invt_bbr, concat_mats, [('out_file', 'in_file2')]),
        (sepair_wf, aw_fmap_unmasked_epi, [('outputnode.fmap_unmasked', 'in_file')]),
        (EPI_BET, aw_fmap_unmasked_epi, [('out_file', 'ref_file')]),
        (concat_mats, aw_fmap_unmasked_epi, [('out_file', 'premat')]),
        (aw_fmap_unmasked_epi, fieldmaprads2epi_abs, [('out_file', 'in_file')]),
        (fieldmaprads2epi_abs, fieldmaprads2epi_bin, [('out_file', 'in_file')]),
        (aw_fmap_unmasked_epi, fugue_shift, [('out_file', 'fmap_in_file')]),
        (fieldmaprads2epi_bin, fugue_shift, [('out_file', 'mask_file')]),
        (sbref_wf, convert_fmap_shift, [('outputnode.sbref_unwarped', 'reference')]),
        (fugue_shift, convert_fmap_shift, [('shift_out_file', 'shift_in_file')]),
        (flt_bbr, convert_fmap_shift, [('out_matrix_file', 'postmat')]),
        (motion_correct_epi, convert_fmap_shift, [('mat_file', 'premat')]),
        (inputnode, split_epi, [('epi', 'in_file')]),
        (split_epi, aw_final, [('out_files', 'in_file')]),
        (sbref_wf, aw_final, [('outputnode.sbref_unwarped', 'ref_file')]),
        (convert_fmap_shift, aw_final, [('out_file', 'field_file')]),
        (aw_final, merge_epi, [('out_file', 'in_files')]),
        (merge_epi, epi_mean, [('merged_file', 'in_file')]),
        (strip_corrected_sbref, flt_sbref_brain_t1_brain, [('out_file', 'in_file')]),
        (sbref_wf, flt_sbref_2_T1, [('outputnode.sbref_unwarped', 'in_file')]),
        (flt_sbref_brain_t1_brain, flt_sbref_2_T1, [('out_matrix_file', 'in_matrix_file')]),
        (strip_corrected_sbref, bbr_sbref_2_T1, [('out_file', 'in_file')]),
        (sbref_wf, bbr_sbref_2_T1, [('outputnode.sbref_fmap', 'fieldmap')]),
        (flt_sbref_2_T1, bbr_sbref_2_T1, [('out_matrix_file', 'in_matrix_file')]),
        (bbr_sbref_2_T1, invt_mat, [('out_matrix_file', 'in_file')]),
        (invt_mat, flt_parcels_2_sbref, [('out_file', 'in_matrix_file')]),
        (sbref_wf, flt_parcels_2_sbref, [('outputnode.sbref_unwarped', 'reference')])
    ])

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
