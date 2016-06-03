#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Created on Wed Dec  2 17:35:40 2015

@author: craigmoodie
"""

from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
import nipype.interfaces.io as nio

from .anatomical import t1w_preprocessing
from .fieldmap import se_pair_workflow, fieldmap_to_phasediff
from .sbref import sbref_workflow, sbref_t1_registration
from .epi import epi_unwarp


def fmri_preprocess_single(name='fMRI_prep', settings=None):
    """
    The main fmri preprocessing workflow.
    """

    if settings is None:
        settings = {}

    for key in ['fsl', 'skull_strip', 'epi', 'connectivity']:
        if settings.get(key) is None:
            settings[key] = {}

    if 'dwell_time' not in settings['epi'].keys():
        # pull from effective echo spacing
        settings['epi']['dwell_time'] = 0.000700012460221792


    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(niu.IdentityInterface(
        fields=['fieldmaps', 'fieldmaps_meta', 'epi', 'epi_meta', 'sbref',
                'sbref_meta', 't1']), name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['fieldmap', 'corrected_sbref', 'fmap_mag', 'fmap_mag_brain',
                't1', 'stripped_epi', 'corrected_epi_mean', 'sbref_brain',
                'stripped_epi_mask', 'stripped_t1', 't1_segmentation',
                't1_2_mni', 't1_wm_seg']),
        name='outputnode'
    )
    datasink = pe.Node(
        interface=nio.DataSink(base_directory=settings['output_dir']),
        name="datasink",
        parameterization=False
    )

    t1w_preproc = t1w_preprocessing(settings=settings)
    sepair_wf = se_pair_workflow(settings=settings)
    fmap2phdiff = fieldmap_to_phasediff()
    fmap2phdiff.inputs.inputnode.dwell_time = 0.07
    fmap2phdiff.inputs.inputnode.unwarp_direction = 'x'

    sbref_wf = sbref_workflow(settings=settings)
    sbref_t1 = sbref_t1_registration(settings=settings)
    unwarp_wf = epi_unwarp(settings=settings)


    #  Connecting Workflow pe.Nodes

    workflow.connect([
        (inputnode, t1w_preproc, [('t1', 'inputnode.t1')]),
        (inputnode, sepair_wf, [('fieldmaps', 'inputnode.fieldmaps')]),
        (inputnode, sbref_wf, [('sbref', 'inputnode.sbref')]),
        (inputnode, unwarp_wf, [('epi', 'inputnode.epi')]),

#        (t1w_preproc, sbref_wf, [('outputnode.t1_seg', 'inputnode.t1_seg')]),
        (sepair_wf, sbref_wf, [
            ('outputnode.mag_brain', 'inputnode.fmap_ref_brain'),
            ('outputnode.fmap_mask', 'inputnode.fmap_mask'),
            ('outputnode.fmap_fieldcoef', 'inputnode.fmap_fieldcoef'),
            ('outputnode.fmap_movpar', 'inputnode.fmap_movpar')
        ]),
        (sbref_wf, sbref_t1, [
            ('outputnode.sbref_unwarped', 'inputnode.sbref_brain')]),
        (t1w_preproc, sbref_t1, [
            ('outputnode.t1_brain', 'inputnode.t1_brain'),
            ('outputnode.t1_seg', 'inputnode.t1_seg')]),
        (sbref_wf, unwarp_wf, [
            ('outputnode.sbref_unwarped', 'inputnode.sbref_brain')]),
        (sepair_wf, unwarp_wf, [
            ('outputnode.fmap_fieldcoef', 'inputnode.fmap_fieldcoef'),
            ('outputnode.fmap_movpar', 'inputnode.fmap_movpar')
        ]),
#        (sepair_wf, fmap2phdiff, [
#            ('outputnode.out_field', 'inputnode.fieldmap'),
#            ('outputnode.fmap_mask', 'inputnode.fmap_mask')
#        ]),
#        (fmap2phdiff, sbref_wf, [
#            ('outputnode.fmap_rads', 'inputnode.fmap_scaled'),
#            ('outputnode.fmap_unmasked', 'inputnode.fmap_unmasked')
#        ]),
#        (t1w_preproc, unwarp_wf, [('outputnode.t1_brain', 'inputnode.t1_brain')]),
#
#        #(t1w_preproc, sbref_wf, [
#        #    ('outputnode.bias_corrected_t1', 'inputnode.t1'),
#        #    ('outputnode.t1_brain', 'inputnode.t1_brain')
#        #]),
#        (fmap2phdiff, unwarp_wf, [
#            ('outputnode.fmap_unmasked', 'inputnode.fmap_unmasked')
#        ]),
#        (sbref_wf, unwarp_wf, [
#            ('outputnode.sbref_brain_corrected', 'inputnode.sbref_brain'),
#            ('outputnode.sbref_unwarped', 'inputnode.sbref_unwarped'),
#            ('outputnode.sbref_fmap', 'inputnode.sbref_fmap'),
#            ('outputnode.mag2sbref_matrix', 'inputnode.mag2sbref_matrix'),
#            ('outputnode.wm_seg', 'inputnode.wm_seg'),
#        ]),
#        (sbref_wf, outputnode, [
#            ('outputnode.sbref_fmap', 'fieldmap'),
#            ('outputnode.sbref_brain', 'sbref_brain'),
#            ('outputnode.sbref_unwarped', 'corrected_sbref'),
#            ('outputnode.sbref_2_t1_transform', 'sbref_2_t1_transform'),
#        ]),
#        (sepair_wf, outputnode, [
#            ('outputnode.out_topup', 'fmap_mag'),
#            ('outputnode.mag_brain', 'fmap_mag_brain')
#        ]),
#        (t1w_preproc, outputnode, [
#            ('outputnode.bias_corrected_t1', 't1'),
#            ('outputnode.t1_brain', 't1_brain'),
#            ('outputnode.t1_segmentation', 't1_segmentation'),
#            ('outputnode.t1_seg', 't1_wm_seg'),
#            ('outputnode.t1_2_mni', 't1_2_mni')
#        ]),
#        (unwarp_wf, outputnode, [
#            ('outputnode.stripped_epi', 'stripped_epi'),
#            ('outputnode.corrected_epi_mean', 'corrected_epi_mean')
#        ]),
#        (t1w_preproc, datasink, [
#            ('outputnode.t1_segmentation', 't1_segmentation'),
#            ('outputnode.bias_corrected_t1', 't1'),
#            ('outputnode.t1_brain', 't1_brain'),
#            ('outputnode.t1_2_mni_forward_transform', 't1_2_mni_forward_transform'),
#            ('outputnode.t1_2_mni_reverse_transform', 't1_2_mni_reverse_transform')
#        ]),
#        (unwarp_wf, datasink, [
#            ('outputnode.stripped_epi_mask', 'stripped_epi_mask'),
#            #  this could use a better name, its the
#            #  unwarped epi in sbref space
#            ('outputnode.merged_epi', 'merged_epi'),
#            ('outputnode.epi_motion_params', 'epi_motion_params')
#        ])
    ])

    return workflow
