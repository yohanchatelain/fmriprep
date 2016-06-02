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

from nipype.interfaces import ants
from nipype.interfaces import fsl
from nipype.interfaces import io as nio
from nipype.interfaces import utility as niu
from nipype.pipeline import engine as pe

from mriqc.workflows.anatomical import mri_reorient_wf

from ..data import get_ants_oasis_template_ras, get_mni_template
from ..viz import stripped_brain_overlay, anatomical_overlay


#  pylint: disable=R0914
def t1w_preprocessing(name='t1w_preprocessing', settings=None):
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
            fields=['wm_seg', 'bias_corrected_t1', 'stripped_t1', "t1_2_mni",
                    't1_2_mni_forward_transform', 't1_2_mni_reverse_transform',
                    'sbref_2_t1_transform', 't1_segmentation']
        ),
        name='outputnode'
    )

    # Reorient T1
    arw = mri_reorient_wf()

    #  T1 Bias Field Correction
    inu_n4 = pe.Node(ants.N4BiasFieldCorrection(dimension=3), name="Bias_Field_Correction")

    t1_skull_strip = pe.Node(ants.segmentation.BrainExtraction(
        dimension=3, use_floatingpoint_precision=1,
        debug=settings['debug']), name="Ants_T1_Brain_Extraction")
    t1_skull_strip.inputs.brain_template = op.join(get_ants_oasis_template_ras(),
                                                   "T_template0.nii.gz")
    t1_skull_strip.inputs.brain_probability_mask = op.join(
        get_ants_oasis_template_ras(),
        "T_template0_BrainCerebellumProbabilityMask.nii.gz"
    )
    t1_skull_strip.inputs.extraction_registration_mask = op.join(
        get_ants_oasis_template_ras(),
        "T_template0_BrainCerebellumRegistrationMask.nii.gz"
    )

    # fast -o fast_test -N -v
    # ../Preprocessing_test_workflow/_subject_id_S2529LVY1263171/Bias_Field_Correction/sub-S2529LVY1263171_run-1_T1w_corrected.nii.gz
    t1_seg = pe.Node(fsl.FAST(no_bias=True), name="T1_Segmentation")

    # Affine transform of T1 segmentation into SBRref space
    flt_wmseg_sbref = pe.Node(fsl.FLIRT(dof=6, bins=640, cost_func='mutualinfo'),
                              name="WMSeg_2_SBRef_Brain_Affine_Transform")

    invert_wmseg_sbref = pe.Node(
        fsl.ConvertXFM(invert_xfm=True), name="invert_wmseg_sbref"
    )

    t1_2_mni = pe.Node(ants.Registration(), name="T1_2_MNI_Registration")
    t1_2_mni.inputs.fixed_image = op.join(get_mni_template(), 'MNI152_T1_2mm.nii.gz')
    t1_2_mni.inputs.fixed_image_mask = op.join(
        get_mni_template(), 'MNI152_T1_2mm_brain_mask.nii.gz')

    # Hack to avoid re-running ANTs all the times
    grabber_interface = nio.JSONFileGrabber()
    setattr(grabber_interface, '_always_run', False)
    t1_2_mni_params = pe.Node(grabber_interface, name='t1_2_mni_params')
    t1_2_mni_params.inputs.in_file = (
        pkgr.resource_filename('fmriprep', 'data/registration_settings.json')
    )

    workflow.connect([
        (inputnode, arw, [('t1', 'inputnode.in_file')]),
        (inputnode, flt_wmseg_sbref, [('sbref', 'reference')]),
        (arw, inu_n4, [('outputnode.out_file', 'input_image')]),
        (inu_n4, t1_skull_strip, [('output_image', 'anatomical_image')]),
        (t1_skull_strip, t1_seg, [('BrainExtractionBrain', 'in_files')]),
        (t1_seg, flt_wmseg_sbref, [('tissue_class_map', 'in_file')]),
        (inu_n4, t1_2_mni, [('output_image', 'moving_image')]),
        (t1_skull_strip, t1_2_mni, [('BrainExtractionMask', 'moving_image_mask')]),
        (flt_wmseg_sbref, invert_wmseg_sbref, [('out_matrix_file', 'in_file')]),
        (flt_wmseg_sbref, outputnode, [('out_file', 'wm_seg')]),
        (invert_wmseg_sbref, outputnode, [('out_file', 'sbref_2_t1_transform')]),
        (inu_n4, outputnode, [('output_image', 'bias_corrected_t1')]),
        (t1_seg, outputnode, [('tissue_class_map', 't1_segmentation')]),
        (t1_2_mni, outputnode, [
            ('warped_image', 't1_2_mni'),
            ('forward_transforms', 't1_2_mni_forward_transform'),
            ('reverse_transforms', 't1_2_mni_reverse_transform')
        ]),
        (t1_skull_strip, outputnode, [
            ('BrainExtractionBrain', 'stripped_t1')]),
    ])

    # Connect reporting nodes
    t1_stripped_overlay = pe.Node(niu.Function(
        input_names=["in_file", "overlay_file", "out_file"], output_names=["out_file"],
        function=stripped_brain_overlay), name="PNG_T1_SkullStrip")
    t1_stripped_overlay.inputs.out_file = "t1_stripped_overlay.png"

    # The T1-to-MNI will be plotted using the segmentation. That's why we transform it first
    seg_2_mni = pe.Node(ants.ApplyTransforms(
        dimension=3, default_value=0, interpolation='NearestNeighbor'), name='Seg-2-MNI-warp')

    t1_2_mni_overlay = pe.Node(niu.Function(
        input_names=["in_file", "overlay_file", "out_file"], output_names=["out_file"],
        function=anatomical_overlay), name="PNG_T1-to-MNI")
    t1_2_mni_overlay.inputs.out_file = "t1_to_mni_overlay.png"
    t1_2_mni_overlay.inputs.overlay_file = op.join(get_mni_template(),
                                           'MNI152_T1_2mm.nii.gz')

    datasink = pe.Node(
        interface=nio.DataSink(
            base_directory=op.join(settings['work_dir'], "images")),
        name="datasink",
        parameterization=False
    )

    workflow.connect([
        (inu_n4, t1_stripped_overlay, [('output_image', 'overlay_file')]),
        (t1_skull_strip, t1_stripped_overlay, [('BrainExtractionMask', 'in_file')]),
        (t1_stripped_overlay, datasink, [('out_file', '@t1_stripped_overlay')]),
        (t1_seg, seg_2_mni, [('tissue_class_map', 'input_image')]),
        (t1_2_mni, seg_2_mni, [('forward_transforms', 'transforms'),
                               ('forward_invert_flags', 'invert_transform_flags')]),
        (seg_2_mni, t1_2_mni_overlay, [('output_image', 'in_file')])
    ])

    # ANTs inputs connected here for clarity
    workflow.connect([
        (t1_2_mni_params, t1_2_mni, [
            ('metric', 'metric'),
            ('metric_weight', 'metric_weight'),
            ('dimension', 'dimension'),
            ('write_composite_transform', 'write_composite_transform'),
            ('radius_or_number_of_bins', 'radius_or_number_of_bins'),
            ('shrink_factors', 'shrink_factors'),
            ('smoothing_sigmas', 'smoothing_sigmas'),
            ('sigma_units', 'sigma_units'),
            ('output_transform_prefix', 'output_transform_prefix'),
            ('transforms', 'transforms'),
            ('transform_parameters', 'transform_parameters'),
            ('initial_moving_transform_com', 'initial_moving_transform_com'),
            ('number_of_iterations', 'number_of_iterations'),
            ('convergence_threshold', 'convergence_threshold'),
            ('convergence_window_size', 'convergence_window_size'),
            ('sampling_strategy', 'sampling_strategy'),
            ('sampling_percentage', 'sampling_percentage'),
            ('output_warped_image', 'output_warped_image'),
            ('use_histogram_matching', 'use_histogram_matching'),
            ('use_estimate_learning_rate_once',
             'use_estimate_learning_rate_once'),
            ('collapse_output_transforms', 'collapse_output_transforms'),
            ('winsorize_lower_quantile', 'winsorize_lower_quantile'),
            ('winsorize_upper_quantile', 'winsorize_upper_quantile'),
        ])
    ])

    return workflow
