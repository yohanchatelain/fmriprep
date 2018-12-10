#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Utilities to handle BIDS inputs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fetch some test data

    >>> import os
    >>> from niworkflows import data
    >>> data_root = data.get_bids_examples(variant='BIDS-examples-1-enh-ds054')
    >>> os.chdir(data_root)

"""
import os
import json


def write_derivative_description(bids_dir, deriv_dir):
    from fmriprep import __version__
    from fmriprep.__about__ import DOWNLOAD_URL

    desc = {
        'Name': 'fMRIPrep output',
        'BIDSVersion': '1.1.1',
        'PipelineDescription': {
            'Name': 'fMRIPrep',
            'Version': __version__,
            'CodeURL': DOWNLOAD_URL,
        },
        'CodeURL': 'https://github.com/poldracklab/fmriprep',
        'HowToAcknowledge':
            'Please cite our paper (https://doi.org/10.1101/306951), and '
            'include the generated citation boilerplate within the Methods '
            'section of the text.',
    }

    # Keys that can only be set by environment
    if 'FMRIPREP_DOCKER_TAG' in os.environ:
        desc['DockerHubContainerTag'] = os.environ['FMRIPREP_DOCKER_TAG']
    if 'FMRIPREP_SINGULARITY_URL' in os.environ:
        singularity_url = os.environ['FMRIPREP_SINGULARITY_URL']
        desc['SingularityContainerURL'] = singularity_url
        try:
            desc['SingularityContainerMD5'] = _get_shub_version(singularity_url)
        except ValueError:
            pass

    # Keys deriving from source dataset
    fname = os.path.join(bids_dir, 'dataset_description.json')
    if os.path.exists(fname):
        with open(fname) as fobj:
            orig_desc = json.load(fobj)
    else:
        orig_desc = {}

    if 'DatasetDOI' in orig_desc:
        desc['SourceDatasetsURLs'] = ['https://doi.org/{}'.format(
            orig_desc['DatasetDOI'])]
    if 'License' in orig_desc:
        desc['License'] = orig_desc['License']

    with open(os.path.join(deriv_dir, 'dataset_description.json'), 'w') as fobj:
        json.dump(desc, fobj, indent=4)


def _get_shub_version(singularity_url):
    raise ValueError("Not yet implemented")
