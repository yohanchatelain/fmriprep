# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Generate T2* map from multi-echo BOLD images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_bold_t2s_wf

"""
from niworkflows.nipype import logging
from niworkflows.nipype.pipeline import engine as pe
from niworkflows.nipype.interfaces import utility as niu
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms

from ...interfaces.multiecho import T2SMap

DEFAULT_MEMORY_MIN_GB = 0.01
LOGGER = logging.getLogger('workflow')


# pylint: disable=R0914
def init_bold_t2s_wf(mem_gb, omp_nthreads, name='bold_t2s_wf'):
    """

    .. workflow::
        :graph2use: orig
        :simple_form: yes

        from fmriprep.workflows.bold import init_bold_t2s_wf
        wf = init_bold_t2s_wf(mem_gb=3,
                              omp_nthreads=1)

    **Parameters**

        mem_gb : float
            Size of BOLD file in GB
        omp_nthreads : int
            Maximum number of threads an individual process may use
        name : str
            Name of workflow (default: ``bold_t2s_wf``)

    **Inputs**

        xforms
            ITKTransform file aligning each volume to ``ref_image``
        bold_file
            list of multi-echo BOLD EPIs

    **Outputs**

        t2s_map
            the T2* map for the EPI run
    """
    workflow = pe.Workflow(name=name)
    inputnode = pe.Node(niu.IdentityInterface(fields=['bold_file', 'xforms']), name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(fields=['t2s_map']), name='outputnode')

    LOGGER.log(25, 'Generating T2* map.')

    apply_hmc = pe.Node(
        ApplyTransforms(interpolation='NearestNeighbor', float=True),
        name='hmc_xforms', mem_gb=0.1)

    t2s_map = pe.Node(T2SMap(tes=tes), name='t2s_map')

    workflow.connect([
        (inputnode, apply_hmc, [('hmc_xforms', 'transforms')]),
        (apply_hmc, t2s_map, [('output_image', 'input_files')]),
        (t2s_map, outputnode, [('bold_file', 't2s_map')]),
    ])

    return workflow
