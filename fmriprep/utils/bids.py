#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Utilities to handle BIDS inputs
"""
import os.path as op
import warnings
from glob import glob
from copy import deepcopy
from bids.grabbids import BIDSLayout

INPUTS_SPEC = {'fieldmaps': [], 'func': [], 't1': [], 'sbref': [], 't2w': []}


def collect_participants(bids_dir, participant_label=None):
    """
    Lists the participants under the BIDS root and checks that participants
    designated with the participant_label argument exist in that folder.

    Returns the list of participants to be finally processed.


    """
    bids_dir = op.abspath(bids_dir)
    all_participants = [op.basename(subdir)[4:]
                        for subdir in glob(op.join(bids_dir, 'sub-*'))]

    # Error: bids_dir does not contain subjects
    if not all_participants:
        raise RuntimeError(
            'Could not find participants in "{}". Please make sure the BIDS data '
            'structure is present and correct. Datasets can be validated online '
            'using the BIDS Validator (http://incf.github.io/bids-validator/).\n'
            'If you are using Docker for Mac or Docker for Windows, you '
            'may need to adjust your "File sharing" preferences.'.format(bids_dir))

    if participant_label is None or not participant_label:
        return all_participants

    # Drop sub- prefixes
    participant_label = [sub[4:] if sub.startswith('sub-') else sub for sub in participant_label]
    # Remove duplicates
    participant_label = list(set(participant_label))
    # Remove labels not found
    found_label = list(set(participant_label) & set(all_participants))
    if not found_label:
        raise RuntimeError('Could not find participants [{}] in folder '
                           '"{}".'.format(', '.join(participant_label), bids_dir))

    notfound_label = list(set(participant_label) - set(all_participants))
    if notfound_label:
        warnings.warn('Some participants were not found: {}'.format(
            ', '.join(notfound_label)), RuntimeWarning)
    return found_label


def collect_data(dataset, subject, task=None, session=None, run=None):
    """
    Uses grabbids to retrieve the input data
    """

    subject = str(subject)
    if subject.startswith('sub-'):
        subject = subject[4:]

    layout = BIDSLayout(dataset)

    if session:
        session_list = [session]
    else:
        session_list = layout.unique('session')
        if session_list == []:
            session_list = [None]

    if run:
        run_list = [run]
    else:
        run_list = layout.unique('run')
        if run_list == []:
            run_list = [None]

    queries = {
        'fmap': {'modality': 'fmap', 'extensions': ['nii', 'nii.gz']},
        'epi': {'modality': 'func', 'type': 'bold', 'extensions': ['nii', 'nii.gz']},
        'sbref': {'modality': 'func', 'type': 'sbref', 'extensions': ['nii', 'nii.gz']},
        't1w': {'type': 'T1w', 'extensions': ['nii', 'nii.gz']},
        't2w': {'type': 'T2w', 'extensions': ['nii', 'nii.gz']},
    }

    if task:
        queries['epi']['task'] = task

    #  Add a subject key pair to each query we make so that we only deal with
    #  files related to this workflows specific subject. Could be made opt...
    for key in queries.keys():
        queries[key]['subject'] = subject

    imaging_data = deepcopy(INPUTS_SPEC)
    fieldmap_files = [x.filename for x in layout.get(**queries['fmap'])]
    imaging_data['fmap'] = fieldmap_files
    t1_files = [x.filename for x in layout.get(**queries['t1w'])]
    imaging_data['t1w'] = t1_files
    sbref_files = [x.filename for x in layout.get(**queries['sbref'])]
    imaging_data['sbref'] = sbref_files
    epi_files = [x.filename for x in layout.get(**queries['epi'])]
    imaging_data['func'] = epi_files
    t2_files = [x.filename for x in layout.get(**queries['t2w'])]
    imaging_data['t2w'] = t2_files

    '''
    loop_on = ['session', 'run', 'acquisition', 'task']
    get_kwargs = {}

    for key in loop_on:
        unique_list = layout.unique(key)
        if unique_list:
            get_kwargs[key] = unique_list

    query_kwargs = []
    for key in get_kwargs:
        query_kwargs.append([(key, x) for x in get_kwargs[key]])

    query_kwargs = itertools.product(*query_kwargs)

    for elem in query_kwargs:
        epi_files = [x.filename for x
                     in layout.get(**dict(dict(elem), **queries['epi']))]
        if epi_files:
            imaging_data['func'] += epi_files
    '''

    return imaging_data
