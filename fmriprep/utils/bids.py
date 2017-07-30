#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Utilities to handle BIDS inputs
"""
import os
import os.path as op
import warnings
from bids.grabbids import BIDSLayout


def collect_participants(bids_dir, participant_label=None):
    """
    Lists the participants under the BIDS root and checks that participants
    designated with the participant_label argument exist in that folder.

    Returns the list of participants to be finally processed.


    """
    bids_dir = op.abspath(bids_dir)
    all_participants = sorted(
        [subdir[4:] for subdir in os.listdir(bids_dir)
         if op.isdir(op.join(bids_dir, subdir)) and subdir.startswith('sub-')])

    # Error: bids_dir does not contain subjects
    if not all_participants:
        raise RuntimeError(
            'Could not find participants in "{}". Please make sure the BIDS data '
            'structure is present and correct. Datasets can be validated online '
            'using the BIDS Validator (http://incf.github.io/bids-validator/).\n'
            'If you are using Docker for Mac or Docker for Windows, you '
            'may need to adjust your "File sharing" preferences.'.format(bids_dir))

    # No --participant-label was set, return all
    if participant_label is None or not participant_label:
        return all_participants

    # Drop sub- prefixes
    participant_label = [sub[4:] if sub.startswith('sub-') else sub for sub in participant_label]
    # Remove duplicates
    participant_label = sorted(list(set(participant_label)))
    # Remove labels not found
    found_label = sorted(list(set(participant_label) & set(all_participants)))
    if not found_label:
        raise RuntimeError('Could not find participants [{}] in folder '
                           '"{}".'.format(', '.join(participant_label), bids_dir))

    # Warn if some IDs were not found
    notfound_label = list(set(participant_label) - set(all_participants))
    if notfound_label:
        warnings.warn('Some participants were not found: {}'.format(
            ', '.join(notfound_label)), RuntimeWarning)
    return found_label


def collect_data(dataset, subject, task=None):
    """
    Uses grabbids to retrieve the input data
    """
    layout = BIDSLayout(dataset)
    queries = {
        'fmap': {'subject': subject, 'modality': 'fmap', 'extensions': ['nii', 'nii.gz']},
        'bold': {'subject': subject, 'modality': 'func', 'type': 'bold',
                 'extensions': ['nii', 'nii.gz']},
        'sbref': {'subject': subject, 'modality': 'func', 'type': 'sbref',
                  'extensions': ['nii', 'nii.gz']},
        't1w': {'subject': subject, 'type': 'T1w', 'extensions': ['nii', 'nii.gz']},
        't2w': {'subject': subject, 'type': 'T2w', 'extensions': ['nii', 'nii.gz']},
    }

    if task:
        queries['bold']['task'] = task

    return {modality: [x.filename for x in layout.get(**query)]
            for modality, query in queries.items()}
