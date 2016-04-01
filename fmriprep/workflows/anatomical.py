#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Anatomical Reference -processing workflows.

Originally coded by Craig Moodie. Refactored by the CRN Developers.

"""
import os
import os.path as op
import pkg_resources as pkgr

from nipype.interfaces import utility as niu
from nipype.interfaces import ants
from nipype.interfaces import fsl
from nipype.pipeline import engine as pe

def t1w_preprocessing(name='t1w_preprocessing', settings=None):  # pylint: disable=R0914
    """T1w images preprocessing pipeline"""

    if settings is None:
        settings = {}
    dwell_time = settings['epi'].get('dwell_time', 0.000700012460221792)

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['t1', 'sbref', 'sbref_brain_corrected', 'sbref_fmap',
                'sbref_unwarped']), name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(fields=['wm_seg']), name='outputnode')


    # T1 Bias Field Correction
    inu_n4 = pe.Node(ants.N4BiasFieldCorrection(
        dimension=3, bspline_fitting_distance=300, shrink_factor=3), name="Bias_Field_Correction")

    # Skull strip the T1 with ANTS Brain Extraction
    t1_brain = pe.Node(
        ants.BrainExtraction(dimension=3), name="antsreg_T1_Brain_Extraction")
    t1_brain.inputs.brain_template = settings['skull_strip'].get(
        'brain_template', pkgr.resource_filename('fmriprep', 'data/brain_template.nii.gz'))
    t1_brain.inputs.brain_probability_mask = settings['skull_strip'].get(
        'brain_probmask', pkgr.resource_filename('fmriprep', 'data/brain_probmask.nii.gz'))
    t1_brain.inputs.extraction_registration_mask = settings[
        'skull_strip'].get('reg_mask', pkgr.resource_filename('fmriprep', 'data/reg_mask.nii.gz'))

    # ANTs registration
    antsreg = pe.Node(ants.Registration(), name="T1_2_MNI_Registration")
    antsreg.inputs.fixed_image = settings['fsl'].get('mni_template', os.path.join(
        os.getenv('FSLDIR'), 'data/standard/MNI152_T1_2mm_brain.nii.gz'))
    antsreg.inputs.metric = ['Mattes'] * 3 + [['Mattes', 'CC']]
    antsreg.inputs.metric_weight = [1] * 3 + [[0.5, 0.5]]
    antsreg.inputs.dimension = 3
    antsreg.inputs.write_composite_transform = True
    antsreg.inputs.radius_or_number_of_bins = [32] * 3 + [[32, 4]]
    antsreg.inputs.shrink_factors = [[6, 4, 2]] + [[3, 2, 1]]*2 + [[4, 2, 1]]
    antsreg.inputs.smoothing_sigmas = [[4, 2, 1]] * 3 + [[1, 0.5, 0]]
    antsreg.inputs.sigma_units = ['vox'] * 4
    antsreg.inputs.output_transform_prefix = "ANTS_T1_2_MNI"
    antsreg.inputs.transforms = ['Translation', 'Rigid', 'Affine', 'SyN']
    antsreg.inputs.transform_parameters = [
        (0.1,), (0.1,), (0.1,), (0.2, 3.0, 0.0)]
    antsreg.inputs.initial_moving_transform_com = True
    antsreg.inputs.number_of_iterations = ([[10, 10, 10]]*3 + [[1, 5, 3]])
    antsreg.inputs.convergence_threshold = [1.e-8] * 3 + [-0.01]
    antsreg.inputs.convergence_window_size = [20] * 3 + [5]
    antsreg.inputs.sampling_strategy = ['Regular'] * 3 + [[None, None]]
    antsreg.inputs.sampling_percentage = [0.3] * 3 + [[None, None]]
    antsreg.inputs.output_warped_image = True
    antsreg.inputs.use_histogram_matching = [False] * 3 + [True]
    antsreg.inputs.use_estimate_learning_rate_once = [True] * 4
    #antsreg.inputs.interpolation = 'NearestNeighbor'

    # Transforming parcels from stan
    applyxfm = pe.Node(ants.ApplyTransforms(dimension=3, interpolation='NearestNeighbor',
                                 default_value=0), name="Apply_ANTS_transform_MNI_2_T1")
    applyxfm.inputs.input_image = settings['connectivity'].get(
        'parellation', pkgr.resource_filename('fmriprep', 'data/parcellation.nii.gz'))

    # fast -o fast_test -N -v
    # ../Preprocessing_test_workflow/_subject_id_S2529LVY1263171/Bias_Field_Correction/sub-S2529LVY1263171_run-1_T1w_corrected.nii.gz
    t1_seg = pe.Node(fsl.FAST(no_bias=True), name="T1_Segmentation")

    # Affine transform of T1 segmentation into SBRref space
    flt_wmseg_sbref = pe.Node(fsl.FLIRT(dof=6, bins=640, cost_func='mutualinfo'),
                              name="WMSeg_2_SBRef_Brain_Affine_Transform")

    flt_sbref_brain_t1_brain = pe.Node(fsl.FLIRT(
        dof=6, bins=640, cost_func='mutualinfo'), name="SBRef_Brain_2_T1_Brain_Affine_Transform")
    flt_sbref_2_T1 = pe.Node(
        fsl.FLIRT(dof=6, bins=640, cost_func='mutualinfo'), name="SBRef_2_T1_Affine_Transform")
    bbr_sbref_2_T1 = pe.Node(
        fsl.FLIRT(dof=6, pedir=1, echospacing=dwell_time, bins=640, cost_func='bbr'), name="BBR_SBRef_to_T1")
    bbr_sbref_2_T1.inputs.schedule = settings['fsl'].get(
        'flirt_bbr', op.join(os.getenv('FSLDIR'), 'etc/flirtsch/bbr.sch'))

    invt_mat = pe.Node(
        fsl.ConvertXFM(invert_xfm=True), name="EpiReg_Inverse_Transform")

    flt_parcels_2_sbref = pe.Node(fsl.FLIRT(
        dof=12, bins=640, cost_func='mutualinfo', interp='nearestneighbour'),
                                  name="Parcels_2_EPI_Mean_Affine_w_Inv_Mat")

    workflow.connect([
        (inputnode, inu_n4, [('t1', 'input_image')]),
        (inputnode, applyxfm, [('t1', 'reference_image')]),
        (inputnode, flt_wmseg_sbref, [('sbref', 'reference')]),

        (inputnode, bbr_sbref_2_T1, [('sbref_brain_corrected', 'in_file'),
                                     ('sbref_fmap', 'fieldmap')]),
        (inputnode, flt_sbref_2_T1, [('sbref_unwarped', 'in_file')]),
        (inputnode, flt_sbref_brain_t1_brain, [('sbref_brain_corrected', 'in_file')]),
        (inputnode, flt_parcels_2_sbref, [('sbref_unwarped', 'reference')]),

        (inu_n4, antsreg, [('output_image', 'moving_image')]),
        (antsreg, applyxfm, [('inverse_composite_transform', 'transforms')]),
        (inu_n4, t1_brain, [('output_image', 'anatomical_image')]),
        (inu_n4, t1_seg, [('output_image', 'in_files')]),
        (t1_seg, flt_wmseg_sbref, [('tissue_class_map', 'in_file')]),

        (flt_sbref_brain_t1_brain, flt_sbref_2_T1, [('out_matrix_file', 'in_matrix_file')]),
        (flt_sbref_2_T1, bbr_sbref_2_T1, [('out_matrix_file', 'in_matrix_file')]),
        (bbr_sbref_2_T1, invt_mat, [('out_matrix_file', 'in_file')]),
        (invt_mat, flt_parcels_2_sbref, [('out_file', 'in_matrix_file')]),
        (t1_seg, bbr_sbref_2_T1, [('tissue_class_map', 'wm_seg')]),
        (inu_n4, flt_parcels_2_sbref, [('output_image', 'in_file')]),
        (inu_n4, flt_sbref_2_T1, [('output_image', 'reference')]),
        (inu_n4, bbr_sbref_2_T1, [('output_image', 'reference')]),
        (t1_brain, flt_sbref_brain_t1_brain, [('BrainExtractionBrain', 'reference')]),

        (flt_wmseg_sbref, outputnode, [('out_file', 'wm_seg')])
    ])

    return workflow
