#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Created on Wed Dec  2 17:35:40 2015

@author: craigmoodie
"""
from __future__ import print_function, division, absolute_import, unicode_literals

import os
from copy import deepcopy

from nipype.pipeline import engine as pe
from nipype.interfaces import fsl
from nipype.interfaces import utility as niu

from fmriprep.interfaces import BIDSDataGrabber, BIDSFreeSurferDir
from fmriprep.utils.misc import collect_bids_data, get_biggest_epi_file_size_gb
from fmriprep.workflows import confounds

from fmriprep.workflows.anatomical import t1w_preprocessing
from fmriprep.workflows.sbref import sbref_preprocess

from fmriprep.workflows.epi import (
    epi_unwarp, epi_hmc, epi_sbref_registration, bold_preprocessing,
    ref_epi_t1_registration)

from bids.grabbids import BIDSLayout


def base_workflow_enumerator(subject_list, task_id, settings, run_uuid):
    workflow = pe.Workflow(name='workflow_enumerator')

    if settings.get('freesurfer', False):
        fsdir = pe.Node(BIDSFreeSurferDir(), name='BIDSFreesurfer')
        fsdir.inputs.freesurfer_home = os.getenv('FREESURFER_HOME')
        fsdir.inputs.derivatives = os.path.join(settings['output_dir'])

    for subject in subject_list:
        generated_workflow = base_workflow_generator(subject, task_id=task_id,
                                                     settings=settings)
        if generated_workflow:
            generated_workflow.config['execution']['crashdump_dir'] = (
                os.path.join(settings['output_dir'], "fmriprep", "sub-" + subject, 'log', run_uuid)
            )
            for node in generated_workflow._get_all_nodes():
                node.config = deepcopy(generated_workflow.config)
            if settings.get('freesurfer', False):
                workflow.connect(fsdir, 'subjects_dir',
                                 generated_workflow, 'inputnode.subjects_dir')
            else:
                workflow.add_nodes([generated_workflow])

    return workflow


def base_workflow_generator(subject_id, task_id, settings):
    subject_data = collect_bids_data(settings['bids_root'], subject_id, task_id)

    settings["biggest_epi_file_size_gb"] = get_biggest_epi_file_size_gb(subject_data['func'])

    if subject_data['func'] == []:
        raise Exception("No BOLD images found for participant {} and task {}. "
                        "All workflows require BOLD images.".format(
                            subject_id, task_id if task_id else '<all>'))

    if subject_data['t1w'] == []:
        raise Exception("No T1w images found for participant {}. "
                        "All workflows require T1w images.".format(subject_id))


    if all((subject_data['fmap'] != [],
            subject_data['sbref'] != [],
            "sbref" not in settings.get('ignore', []))):
        return basic_fmap_sbref_wf(subject_data, settings, name=subject_id)
    else:
        return basic_wf(subject_data, settings, name=subject_id)


def basic_fmap_sbref_wf(subject_data, settings, name='fMRI_prep'):
    """
    The main fmri preprocessing workflow, for the ds054-type of data:

      * [x] Has at least one T1w and at least one bold file (minimal reqs.)
      * [x] Has one or more SBRefs
      * [x] Has fieldmaps in one of the following options:
        * [x] Phase-difference: one or more GRE-phasediff images, including
              the corresponding magnitude images.
        * [x] "Natural" fieldmaps: spiral field-mapping sequences
        * [x] "PEPolar": :abbr:`PE (phase-encoding)` varying *Polar*ity images

    """

    if settings is None:
        settings = {}

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=['subjects_dir']),
                        name='inputnode')
    #  inputnode = pe.Node(niu.IdentityInterface(fields=['subject_id']),
    #                    name='inputnode')
    #  inputnode.iterables = [('subject_id', subject_list)]

    bidssrc = pe.Node(BIDSDataGrabber(subject_data=subject_data), name='BIDSDatasource')

    # Preprocessing of T1w (includes registration to MNI)
    t1w_pre = t1w_preprocessing(settings=settings)

    # Estimate fieldmap
    fmap_est = None
    if 'fieldmap' not in settings.get('ignore', []):
        # Import specific workflows here, so we don't brake everything with one
        # unused workflow.
        from fmriprep.workflows.fieldmap import fmap_estimator
        fmap_est = fmap_estimator(subject_data, settings=settings)

    if fmap_est is None:
        # Fallback to non-fieldmap workflow
        settings['ignore'] = settings.get('ignore', []) + ['fieldmap']
        return basic_wf(subject_data, settings=settings)

    # Correct SBRef
    sbref_pre = sbref_preprocess(settings=settings)

    # Register SBRef to T1
    sbref_t1 = ref_epi_t1_registration(reportlet_suffix='sbref_t1_bbr',
                                       inv_ds_suffix='target-sbref_affine',
                                       settings=settings)

    # HMC on the EPI
    hmcwf = epi_hmc(settings=settings)
    hmcwf.get_node('inputnode').iterables = ('epi', subject_data['func'])

    # EPI to SBRef
    epi2sbref = epi_sbref_registration(settings)

    # EPI unwarp
    epiunwarp_wf = epi_unwarp(settings=settings)

    # get confounds
    confounds_wf = confounds.discover_wf(settings)
    confounds_wf.get_node('inputnode').inputs.t1_transform_flags = [False, True]

    # create list of transforms to resample t1 -> sbref -> epi
    t1_to_epi_transforms = pe.Node(fsl.ConvertXFM(concat_xfm=True), name='T1ToEPITransforms')

    workflow.connect([
        (bidssrc, t1w_pre, [('t1w', 'inputnode.t1w'),
                            ('t2w', 'inputnode.t2w')]),
        (bidssrc, sbref_pre, [('sbref', 'inputnode.sbref')]),
        (bidssrc, sbref_t1, [('sbref', 'inputnode.name_source'),
                             ('t1w', 'inputnode.t1w')]),
        (fmap_est, sbref_pre, [('outputnode.fmap', 'inputnode.fmap'),
                               ('outputnode.fmap_ref', 'inputnode.fmap_ref'),
                               ('outputnode.fmap_mask', 'inputnode.fmap_mask')]),
        (sbref_pre, sbref_t1, [('outputnode.sbref_unwarped', 'inputnode.ref_epi'),
                               ('outputnode.sbref_unwarped_mask', 'inputnode.ref_epi_mask')]),
        (t1w_pre, sbref_t1, [
            ('outputnode.bias_corrected_t1', 'inputnode.bias_corrected_t1'),
            ('outputnode.t1_mask', 'inputnode.t1_mask'),
            ('outputnode.t1_brain', 'inputnode.t1_brain'),
            ('outputnode.t1_seg', 'inputnode.t1_seg')]),
        (sbref_pre, epi2sbref, [('outputnode.sbref_unwarped', 'inputnode.sbref'),
                                ('outputnode.sbref_unwarped_mask', 'inputnode.sbref_mask')]),
        (hmcwf, epi2sbref, [('outputnode.epi_mask', 'inputnode.epi_mask'),
                            ('outputnode.epi_mean', 'inputnode.epi_mean'),
                            ('outputnode.epi_hmc', 'inputnode.epi'),
                            ('inputnode.epi', 'inputnode.epi_name_source')]),
        (hmcwf, epiunwarp_wf, [('inputnode.epi', 'inputnode.epi')]),
        (fmap_est, epiunwarp_wf, [('outputnode.fmap', 'inputnode.fmap'),
                                  ('outputnode.fmap_mask', 'inputnode.fmap_mask'),
                                  ('outputnode.fmap_ref', 'inputnode.fmap_ref')]),

        (sbref_t1, t1_to_epi_transforms, [(('outputnode.mat_t1_to_epi'), 'in_file')]),
        (epi2sbref, t1_to_epi_transforms, [('outputnode.out_mat_inv', 'in_file2')]),

        (t1_to_epi_transforms, confounds_wf, [('out_file', 'inputnode.t1_transform')]),

        (hmcwf, confounds_wf, [('outputnode.movpar_file', 'inputnode.movpar_file'),
                               ('outputnode.epi_mean', 'inputnode.reference_image'),
                               ('inputnode.epi', 'inputnode.source_file')]),
        (epiunwarp_wf, confounds_wf, [('outputnode.epi_mask', 'inputnode.epi_mask'),
                                      ('outputnode.epi_unwarp', 'inputnode.fmri_file')]),
        (t1w_pre, confounds_wf, [('outputnode.t1_tpms', 'inputnode.t1_tpms')]),
    ])

    if settings.get('freesurfer', False):
        workflow.connect([
            (inputnode, t1w_pre, [('subjects_dir', 'inputnode.subjects_dir')]),
            (inputnode, sbref_t1, [('subjects_dir', 'inputnode.subjects_dir')]),
            (t1w_pre, sbref_t1, [('outputnode.subject_id', 'inputnode.subject_id'),
                                 ('outputnode.fs_2_t1_transform', 'inputnode.fs_2_t1_transform')]),
            ])

    return workflow


def basic_wf(subject_data, settings, name='fMRI_prep'):
    """
    The main fmri preprocessing workflow, for the ds005-type of data:

      * Has at least one T1w and at least one bold file (minimal reqs.)
      * No SBRefs
      * May have fieldmaps

    """

    if settings is None:
        settings = {}

    workflow = pe.Workflow(name=name)

    layout = BIDSLayout(settings["bids_root"])

    inputnode = pe.Node(niu.IdentityInterface(fields=['subjects_dir']),
                        name='inputnode')

    bidssrc = pe.Node(BIDSDataGrabber(subject_data=subject_data),
                      name='BIDSDatasource')

    # Preprocessing of T1w (includes registration to MNI)
    t1w_pre = t1w_preprocessing(settings=settings)

    workflow.connect([
        (bidssrc, t1w_pre, [('t1w', 'inputnode.t1w'),
                            ('t2w', 'inputnode.t2w')]),
    ])

    for bold_file in subject_data['func']:
        bold_pre = bold_preprocessing(bold_file, layout=layout,
                                      settings=settings)

        workflow.connect([
            (bidssrc, bold_pre, [('t1w', 'inputnode.t1w')]),
            (t1w_pre, bold_pre,
             [('outputnode.bias_corrected_t1', 'inputnode.bias_corrected_t1'),
              ('outputnode.t1_brain', 'inputnode.t1_brain'),
              ('outputnode.t1_mask', 'inputnode.t1_mask'),
              ('outputnode.t1_seg', 'inputnode.t1_seg'),
              ('outputnode.t1_tpms', 'inputnode.t1_tpms'),
              ('outputnode.t1_2_mni_forward_transform', 'inputnode.t1_2_mni_forward_transform')])
        ])

        if settings['freesurfer']:
            workflow.connect([
                (inputnode, bold_pre,
                 [('subjects_dir', 'inputnode.subjects_dir')]),
                (t1w_pre, bold_pre,
                 [('outputnode.subject_id', 'inputnode.subject_id'),
                  ('outputnode.fs_2_t1_transform', 'inputnode.fs_2_t1_transform')]),
            ])

    return workflow
