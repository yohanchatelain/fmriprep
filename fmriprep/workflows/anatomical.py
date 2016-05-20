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

from ..data import get_mni_template

def t1w_preprocessing(name='t1w_preprocessing', settings=None):  # pylint: disable=R0914
    """T1w images preprocessing pipeline"""

    if settings is None:
        settings = {}
    dwell_time = settings['epi'].get('dwell_time', 0.000700012460221792)

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['t1', 'sbref', 'sbref_brain_corrected', 'sbref_fmap',
                'sbref_unwarped']), name='inputnode')
    outputnode = pe.Node(
         niu.IdentityInterface(
            fields=['wm_seg', 'bias_corrected_t1', 'stripped_t1', 
                    't1_2_mni_forward_transform', 't1_2_mni_reverse_transform',
                    'sbref_2_t1_transform', 't1_segmentation']
         ), 
         name='outputnode'
    )


    # T1 Bias Field Correction
    inu_n4 = pe.Node(
        ants.N4BiasFieldCorrection(dimension=3, bspline_fitting_distance=300, 
                                   shrink_factor=3), 
        name="Bias_Field_Correction"
    )

    t1_skull_strip = pe.Node(
        fsl.BET(mask=True, functional=True, frac=0.6), name="t1_skull_Strip")
    '''
    t1_skull_strip = Node(ants.segmentation.BrainExtraction(), 
                          name = "Ants_T1_Brain_Extraction")
    t1_skull_strip.inputs.dimension = 3
    t1_skull_strip.inputs.brain_template = "/home/cmoodie/Oasis_MICCAI2012-Multi-Atlas-Challenge-Data/T_template0.nii.gz"
    t1_skull_strip.inputs.brain_probability_mask = "/home/cmoodie/Oasis_MICCAI2012-Multi-Atlas-Challenge-Data/T_template0_BrainCerebellumProbabilityMask.nii.gz"
    t1_skull_strip.inputs.extraction_registration_mask = "/home/cmoodie/Oasis_MICCAI2012-Multi-Atlas-Challenge-Data/T_template0_BrainCerebellumRegistrationMask.nii.gz"
    '''

    # fast -o fast_test -N -v
    # ../Preprocessing_test_workflow/_subject_id_S2529LVY1263171/Bias_Field_Correction/sub-S2529LVY1263171_run-1_T1w_corrected.nii.gz
    t1_seg = pe.Node(fsl.FAST(no_bias=True), name="T1_Segmentation")

    # Affine transform of T1 segmentation into SBRref space
    flt_wmseg_sbref = pe.Node(fsl.FLIRT(dof=6, bins=640, cost_func='mutualinfo'),
                              name="WMSeg_2_SBRef_Brain_Affine_Transform")

    invert_wmseg_sbref = pe.Node(
        fsl.ConvertXFM(invert_xfm = True),
        name="invert_wmseg_sbref"
    )

    t1_2_mni = pe.Node(ants.Registration(), name = "T1_2_MNI_Registration")
    t1_2_mni.inputs.fixed_image = op.join(get_mni_template(), 'MNI152_T1_2mm.nii.gz')
    t1_2_mni.inputs.metric = ['Mattes'] * 3 + [['Mattes', 'CC']]
    t1_2_mni.inputs.metric_weight = [1] * 3 + [[0.5, 0.5]]
    t1_2_mni.inputs.dimension = 3
    t1_2_mni.inputs.write_composite_transform = False
    t1_2_mni.inputs.radius_or_number_of_bins = [32] * 3 + [[32, 4]]
    t1_2_mni.inputs.shrink_factors = [[6, 4, 2]] + [[3, 2, 1]]*2 + [[4, 2, 1]]
    t1_2_mni.inputs.smoothing_sigmas = [[4, 2, 1]] * 3 + [[1, 0.5, 0]]
    t1_2_mni.inputs.sigma_units = ['vox'] * 4
    t1_2_mni.inputs.output_transform_prefix = "ANTS_T1_2_MNI"
    t1_2_mni.inputs.transforms = ['Translation', 'Rigid', 'Affine', 'SyN']
    t1_2_mni.inputs.transform_parameters = [(0.1,), (0.1,), (0.1,), (0.2, 3.0, 0.0)]
    t1_2_mni.inputs.initial_moving_transform_com = True
    t1_2_mni.inputs.number_of_iterations = ([[10, 10, 10]]*3 + [[1, 5, 3]])
    t1_2_mni.inputs.convergence_threshold = [1.e-8] * 3 + [-0.01]
    t1_2_mni.inputs.convergence_window_size = [20] * 3 + [5]
    t1_2_mni.inputs.sampling_strategy = ['Regular'] * 3 + [[None, None]]
    t1_2_mni.inputs.sampling_percentage = [0.3] * 3 + [[None, None]]
    t1_2_mni.inputs.output_warped_image = True
    t1_2_mni.inputs.use_histogram_matching = [False] * 3 + [True]
    t1_2_mni.inputs.use_estimate_learning_rate_once = [True] * 4
    t1_2_mni.inputs.collapse_output_transforms = False

    workflow.connect([
        (inputnode, inu_n4, [('t1', 'input_image')]),
        (inputnode, flt_wmseg_sbref, [('sbref', 'reference')]),
        (inu_n4, t1_seg, [('output_image', 'in_files')]),
        (inu_n4, t1_skull_strip, [('output_image', 'in_file')]),
        (inu_n4, t1_2_mni, [('output_image', 'moving_image')]),
        (t1_seg, flt_wmseg_sbref, [('tissue_class_map', 'in_file')]),
        (flt_wmseg_sbref, outputnode, [('out_file', 'wm_seg')]),
        (flt_wmseg_sbref, invert_wmseg_sbref, [('out_matrix_file', 'in_file')]),
        (invert_wmseg_sbref, outputnode, [('out_file', 'sbref_2_t1_transform')]),
        (inu_n4, outputnode, [('output_image', 'bias_corrected_t1')]),
        (t1_skull_strip, outputnode, [('out_file', 'stripped_t1')]),
        (t1_seg, outputnode, [('tissue_class_map', 't1_segmentation')]),
        (t1_2_mni, outputnode, [('forward_transforms', 't1_2_mni_forward_transform')]),
        (t1_2_mni, outputnode, [('reverse_transforms', 't1_2_mni_reverse_transform')])
    ])

    return workflow
