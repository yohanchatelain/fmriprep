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

from .anatomical import t1w_preprocessing
from .fieldmap import se_pair_workflow
from .epi import sbref_workflow, correction_workflow


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
                't1', 'stripped_epi', 'corrected_epi_mean', 'sbref_brain']),
        name='outputnode'
    )

    t1w_preproc = t1w_preprocessing(settings=settings)
    sepair_wf = se_pair_workflow(settings=settings)
    sbref_wf = sbref_workflow(settings=settings)
    unwarp_wf = correction_workflow(settings=settings)


    #  Connecting Workflow pe.Nodes

    workflow.connect([
        (inputnode, t1w_preproc, [('t1', 'inputnode.t1'),
                                  ('sbref', 'inputnode.sbref')]),
        (inputnode, sepair_wf, [('fieldmaps', 'inputnode.fieldmaps'),
                                ('fieldmaps_meta', 'inputnode.fieldmaps_meta')]),
        (inputnode, unwarp_wf, [('epi', 'inputnode.epi'),
                                ('sbref', 'inputnode.sbref')]),
        (inputnode, sbref_wf, [('sbref', 'inputnode.sbref')]),
        (sbref_wf, t1w_preproc, [
            ('outputnode.sbref_brain_corrected', 'inputnode.sbref_brain_corrected'),
            ('outputnode.sbref_fmap', 'inputnode.sbref_fmap'),
            ('outputnode.sbref_unwarped', 'inputnode.sbref_unwarped')]),
        (sepair_wf, sbref_wf, [('outputnode.fmap_scaled', 'inputnode.fmap_scaled'),
                               ('outputnode.mag_brain', 'inputnode.mag_brain'),
                               ('outputnode.fmap_mask', 'inputnode.fmap_mask'),
                               ('outputnode.out_topup', 'inputnode.in_topup'),
                               ('outputnode.fmap_unmasked', 'inputnode.fmap_unmasked')]),
        (t1w_preproc, unwarp_wf, [('outputnode.wm_seg', 'inputnode.wm_seg')]),
        (sepair_wf, unwarp_wf, [('outputnode.fmap_unmasked', 'inputnode.fmap_unmasked')]),
        (sbref_wf, unwarp_wf, [('outputnode.sbref_brain_corrected', 'inputnode.sbref_brain'),
                               ('outputnode.sbref_unwarped', 'inputnode.sbref_unwarped'),
                               ('outputnode.sbref_fmap', 'inputnode.sbref_fmap'),
                               ('outputnode.mag2sbref_matrix', 'inputnode.mag2sbref_matrix')]),
        (sbref_wf, outputnode, [('outputnode.sbref_fmap', 'fieldmap'),
                                ('outputnode.sbref_brain', 'sbref_brain'),
                                ('outputnode.sbref_unwarped', 'corrected_sbref')]),
        (sepair_wf, outputnode, [('outputnode.out_topup', 'fmap_mag'),
                                 ('outputnode.mag_brain', 'fmap_mag_brain')]),
        (t1w_preproc, outputnode, [('outputnode.bias_corrected_t1', 't1')]),
        (unwarp_wf, outputnode, [('outputnode.stripped_epi', 'stripped_epi'),
                                 ('outputnode.corrected_epi_mean', 'corrected_epi_mean')]),
    ])

    return workflow

def fmri_preprocess(name='fMRI_prep', settings=None, subject_list=None):
    """
    The main fmri preprocessing workflow.
    """

    if settings is None:
        settings = {}

    for key in ['fsl', 'skull_strip', 'epi', 'connectivity']:
        if settings.get(key) is None:
            settings[key] = {}

    if 'dwell_time' not in settings['epi'].keys():
        settings['epi']['dwell_time'] = 0.000700012460221792

    # if subject_list is None or not subject_list:
    #     raise RuntimeError('No subjects were specified')


    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(niu.IdentityInterface(
        fields=['fieldmaps', 'fieldmaps_meta', 'epi', 'epi_meta', 'sbref', 'sbref_meta',
                't1']), name='inputnode')

    t1w_preproc = t1w_preprocessing(settings=settings)
    sepair_wf = se_pair_workflow(settings=settings)
    sbref_wf = sbref_workflow(settings=settings)
    unwarp_wf = correction_workflow(settings=settings)

    # create_parameters_node = pe.Node(niu.Function(
    #     input_names=["fieldmaps", "fieldmaps_meta"], output_names=["parameters_file"],
    #     function=create_encoding_file), name="Create_Parameters", updatehash=True)

    ########################################## Connecting Workflow pe.Nodes ##

    workflow.connect([
        (inputnode, t1w_preproc, [('t1', 'inputnode.t1'),
                                  ('sbref', 'inputnode.sbref')]),
        (inputnode, sepair_wf, [('fieldmaps', 'inputnode.fieldmaps')]),
        (inputnode, unwarp_wf, [('epi', 'inputnode.epi'),
                                ('sbref', 'inputnode.sbref')]),
        (inputnode, sbref_wf, [('sbref', 'inputnode.sbref')]),
        (sbref_wf, t1w_preproc, [
            ('outputnode.sbref_brain_corrected', 'inputnode.sbref_brain_corrected'),
            ('outputnode.sbref_fmap', 'inputnode.sbref_fmap'),
            ('outputnode.sbref_unwarped', 'inputnode.sbref_unwarped')]),
        (sepair_wf, sbref_wf, [('outputnode.fmap_scaled', 'inputnode.fmap_scaled'),
                               ('outputnode.mag_brain', 'inputnode.mag_brain'),
                               ('outputnode.fmap_mask', 'inputnode.fmap_mask'),
                               ('outputnode.out_topup', 'inputnode.in_topup'),
                               ('outputnode.fmap_unmasked', 'inputnode.fmap_unmasked')]),
        (t1w_preproc, unwarp_wf, [('outputnode.wm_seg', 'inputnode.wm_seg')]),
        (sepair_wf, unwarp_wf, [('outputnode.fmap_unmasked', 'inputnode.fmap_unmasked')]),
        (sbref_wf, unwarp_wf, [('outputnode.sbref_brain', 'inputnode.sbref_brain'),
                               ('outputnode.sbref_unwarped', 'inputnode.sbref_unwarped'),
                               ('outputnode.sbref_fmap', 'inputnode.sbref_fmap'),
                               ('outputnode.mag2sbref_matrix', 'inputnode.mag2sbref_matrix')])
        #(inputnode, create_parameters_node, [('fieldmaps', 'fieldmaps')]),
        #(inputnode, create_parameters_node, [('fieldmaps_meta', 'fieldmaps_meta')]),
    ])

    return workflow
