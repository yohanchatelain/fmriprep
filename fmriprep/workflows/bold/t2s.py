# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Generate T2* map from multi-echo BOLD images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_bold_t2s_wf

"""
from nipype import logging
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu

from ...engine import Workflow
from ...interfaces import T2SMap

from .util import init_skullstrip_bold_wf

DEFAULT_MEMORY_MIN_GB = 0.01
LOGGER = logging.getLogger('nipype.workflow')


# pylint: disable=R0914
def init_bold_t2s_wf(echo_times,
                     mem_gb, omp_nthreads,
                     name='bold_t2s_wf'):
    """
    This workflow wraps the `tedana`_ `T2* workflow`_ to optimally
    combine multiple echos and derive a T2* map for use as a
    coregistration target.

    The following steps are performed:

    #. :abbr:`HMC (head motion correction)` on individual echo files.
    #. Compute the adaptive T2* map
    #. Create an optimally combined ME-EPI time series

    **Parameters**

        echo_times
            list of TEs associated with each echo
        mem_gb : float
            Size of BOLD file in GB
        omp_nthreads : int
            Maximum number of threads an individual process may use
        name : str
            Name of workflow (default: ``bold_t2s_wf``)

    **Inputs**

        bold_file
            list of individual echo files

    **Outputs**

        bold
            the optimally combined time series for all supplied echos
        bold_mask
            the skull-stripped adaptive T2* map
        bold_ref
            the adaptive T2* map

    .. _tedana: https://github.com/me-ica/tedana
    .. _`T2* workflow`: https://tedana.readthedocs.io/en/latest/generated/tedana.workflows.t2smap_workflow.html#tedana.workflows.t2smap_workflow  # noqa

    """
    workflow = Workflow(name=name)
    workflow.__desc__ = """\
A T2* map was estimated from preprocessed BOLD by fitting to a
monoexponential signal decay model with log-linear regression.
For each voxel, the maximal number of echoes with high signal in that voxel was
used to fit the model.
The T2* map was used to optimally combine preprocessed BOLD across
echoes following the method described in @posse_t2s and was also retained as
the BOLD reference.
"""

    inputnode = pe.Node(niu.IdentityInterface(fields=['bold_file']), name='inputnode')

    outputnode = pe.Node(niu.IdentityInterface(fields=['bold', 'bold_mask', 'bold_ref']),
                         name='outputnode')

    LOGGER.log(25, 'Generating T2* map and optimally combined ME-EPI time series.')

    t2smap_node = pe.Node(T2SMap(echo_times=echo_times), name='t2smap_node')
    skullstrip_t2smap_wf = init_skullstrip_bold_wf(name='skullstrip_t2smap_wf')

    workflow.connect([
        (inputnode, t2smap_node, [('bold_file', 'in_files')]),
        (t2smap_node, outputnode, [('t2star_adaptive_map', 'bold_ref'),
                                   ('optimal_comb', 'bold')]),
        (t2smap_node, skullstrip_t2smap_wf, [('t2star_adaptive_map', 'inputnode.in_file')]),
        (skullstrip_t2smap_wf, outputnode, [('outputnode.mask_file', 'bold_mask')]),
    ])

    return workflow
