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
from nipype.interfaces import fsl
from nipype.interfaces import freesurfer as fs
import nipype.interfaces.io as nio

from fmriprep.workflows.anatomical import t1w_preprocessing
from fmriprep.workflows.fieldmap.se_pair_workflow import se_pair_workflow
from fmriprep.workflows.fieldmap.fieldmap_to_phasediff import fieldmap_to_phasediff
from fmriprep.workflows.fieldmap.base import fieldmap_decider
from fmriprep.workflows.sbref import sbref_workflow
from fmriprep.workflows import sbref
from fmriprep.workflows.epi import (
    epi_unwarp, epi_hmc, epi_mean_t1_registration, epi_mni_transformation)



def fmriprep_single(subject_data, name='fMRI_prep', settings=None):
    """
    The main fmri preprocessing workflow.
    """

    if settings is None:
        settings = {}

    for key in ['fsl', 'skull_strip', 'epi', 'connectivity']:
        if settings.get(key) is None:
            settings[key] = {}

    sbref_present = len(subject_data['sbref']) > 0

    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(niu.IdentityInterface(
        fields=['fieldmaps', 'fieldmaps_meta', 'epi_meta', 'sbref',
                'sbref_meta', 't1']), name='inputnode')

    # Set inputs: epi is iterable over the available runs
    for key in subject_data.keys():
        if key != 'epi':
            setattr(inputnode.inputs, key, subject_data[key])

    inputfmri = pe.Node(niu.IdentityInterface(
        fields=['epi']), name='inputfmri')
    inputfmri.iterables = [('epi', subject_data['epi'])]


    outputnode = pe.Node(niu.IdentityInterface(
        fields=['fieldmap', 'corrected_sbref', 'fmap_mag', 'fmap_mag_brain',
                't1', 'stripped_epi', 'corrected_epi_mean', 'sbref_brain',
                'stripped_epi_mask', 'stripped_t1', 't1_segmentation',
                't1_2_mni', 't1_wm_seg']),
        name='outputnode'
    )

    try:
        fmap_wf = fieldmap_decider(subject_data, settings)
    except NotImplementedError:
        fmap_wf = None

    # Reorient EPI to RAS
    split = pe.Node(fsl.Split(dimension='t'), name='SplitEPI')
    orient = pe.MapNode(fs.MRIConvert(out_type='niigz', out_orientation='RAS'),
                        iterfield=['in_file'], name='ReorientEPI')
    merge = pe.Node(fsl.Merge(dimension='t'), name='MergeEPI')

    t1w_preproc = t1w_preprocessing(settings=settings)
    epi_hmc_wf = epi_hmc(settings=settings, sbref_present=sbref_present)
    epi_mni_trans_wf = epi_mni_transformation(settings=settings)

    #  Connecting Workflow pe.Nodes
    workflow.connect([
        (inputfmri, split, [('epi', 'in_file')]),
        (split, orient, [('out_files', 'in_file')]),
        (orient, merge, [('out_file', 'in_files')]),

        (inputnode, t1w_preproc, [('t1', 'inputnode.t1')]),
        (merge, epi_hmc_wf, [('merged_file', 'inputnode.epi_ras')]),
        (merge, epi_mni_trans_wf, [('merged_file', 'inputnode.epi_ras')]),

        # These are necessary sources for the DerivativesDataSink
        (inputfmri, epi_hmc_wf, [('epi', 'inputnode.epi')]),
        (inputfmri, epi_mni_trans_wf, [('epi', 'inputnode.epi')])
    ])

    if not sbref_present:
        epi_2_t1 = epi_mean_t1_registration(settings=settings)
        workflow.connect([
            (inputfmri, epi_2_t1, [('epi', 'inputnode.epi')]),
            (epi_hmc_wf, epi_2_t1, [('outputnode.epi_mean', 'inputnode.epi_mean')]),
            (t1w_preproc, epi_2_t1, [('outputnode.t1_brain', 'inputnode.t1_brain'),
                                     ('outputnode.t1_seg', 'inputnode.t1_seg')]),
            (epi_2_t1, epi_mni_trans_wf, [('outputnode.mat_epi_to_t1', 'inputnode.mat_epi_to_t1')]),

            (epi_hmc_wf, epi_mni_trans_wf, [('outputnode.xforms', 'inputnode.hmc_xforms'),
                                            ('outputnode.epi_mask', 'inputnode.epi_mask')]),
            (t1w_preproc, epi_mni_trans_wf, [('outputnode.t1_brain', 'inputnode.t1'),
                                             ('outputnode.t1_2_mni_forward_transform',
                                              'inputnode.t1_2_mni_forward_transform')])
        ])

    if fmap_wf:
        sbref_wf = sbref_workflow(settings=settings)
        sbref_wf.inputs.inputnode.hmc_mats = []  # FIXME: plug MCFLIRT output here
        sbref_t1 = sbref.sbref_t1_registration(settings=settings)
        unwarp_wf = epi_unwarp(settings=settings)
        sepair_wf = se_pair_workflow(settings=settings)
        workflow.connect([
            (inputnode, sepair_wf, [('fieldmaps', 'inputnode.input_images')]),
            (inputnode, sbref_wf, [('sbref', 'inputnode.sbref')]),
            (inputnode, unwarp_wf, [('epi', 'inputnode.epi')]),
            (sepair_wf, sbref_wf, [
                ('outputnode.mag_brain', 'inputnode.fmap_ref_brain'),
                ('outputnode.fmap_mask', 'inputnode.fmap_mask'),
                ('outputnode.fieldmap', 'inputnode.fieldmap')
            ]),
            (sbref_wf, sbref_t1, [
                ('outputnode.sbref_unwarped', 'inputnode.sbref_brain')]),
            (t1w_preproc, sbref_t1, [
                ('outputnode.t1_brain', 'inputnode.t1_brain'),
                ('outputnode.t1_seg', 'inputnode.t1_seg')]),
            (sbref_wf, unwarp_wf, [
                ('outputnode.sbref_unwarped', 'inputnode.sbref_brain')]),
            (sbref_wf, epi_hmc_wf, [
                ('outputnode.sbref_unwarped', 'inputnode.sbref_brain')]),
            (epi_hmc_wf, unwarp_wf, [
                ('outputnode.epi_brain', 'inputnode.epi_brain')]),
            (sepair_wf, unwarp_wf, [
                ('outputnode.fmap_mask', 'inputnode.fmap_mask'),
                ('outputnode.fieldmap', 'inputnode.fieldmap')
            ]),
        ])

    return workflow
