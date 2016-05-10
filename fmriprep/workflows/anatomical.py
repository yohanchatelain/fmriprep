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
    outputnode = pe.Node(
         niu.IdentityInterface(fields=['wm_seg', 'bias_corrected_t1']), 
         name='outputnode'
    )


    # T1 Bias Field Correction
    inu_n4 = pe.Node(ants.N4BiasFieldCorrection(
        dimension=3, bspline_fitting_distance=300, shrink_factor=3), name="Bias_Field_Correction")

    # fast -o fast_test -N -v
    # ../Preprocessing_test_workflow/_subject_id_S2529LVY1263171/Bias_Field_Correction/sub-S2529LVY1263171_run-1_T1w_corrected.nii.gz
    t1_seg = pe.Node(fsl.FAST(no_bias=True), name="T1_Segmentation")

    # Affine transform of T1 segmentation into SBRref space
    flt_wmseg_sbref = pe.Node(fsl.FLIRT(dof=6, bins=640, cost_func='mutualinfo'),
                              name="WMSeg_2_SBRef_Brain_Affine_Transform")

    workflow.connect([
        (inputnode, inu_n4, [('t1', 'input_image')]),
        (inputnode, flt_wmseg_sbref, [('sbref', 'reference')]),
        (inu_n4, t1_seg, [('output_image', 'in_files')]),
        (t1_seg, flt_wmseg_sbref, [('tissue_class_map', 'in_file')]),
        (flt_wmseg_sbref, outputnode, [('out_file', 'wm_seg')]),
        (inu_n4, outputnode, [('output_image', 'bias_corrected_t1')])
    ])

    return workflow
