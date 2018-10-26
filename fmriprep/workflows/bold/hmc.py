# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Head-Motion Estimation and Correction (HMC) of BOLD images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_bold_hmc_wf

"""

from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu, afni, fsl
from niworkflows.interfaces import NormalizeMotionParams
from ...interfaces import Volreg2ITK, MCFLIRT2ITK
from ...engine import Workflow

DEFAULT_MEMORY_MIN_GB = 0.01


# pylint: disable=R0914
def init_bold_hmc_wf(use_mcflirt, mem_gb, omp_nthreads, name='bold_hmc_wf'):
    """
    This workflow estimates the motion parameters to perform
    :abbr:`HMC (head motion correction)` over the input
    :abbr:`BOLD (blood-oxygen-level dependent)` image.

    .. workflow::
        :graph2use: orig
        :simple_form: yes

        from fmriprep.workflows.bold import init_bold_hmc_wf
        wf = init_bold_hmc_wf(
            use_mcflirt=False,
            mem_gb=3,
            omp_nthreads=1)

    **Parameters**

        use_mcflirt : bool
            Use FSL ``mcflirt`` for head motion correction, instead of AFNI ``3dVolreg``.
        mem_gb : float
            Size of BOLD file in GB
        omp_nthreads : int
            Maximum number of threads an individual process may use
        name : str
            Name of workflow (default: ``bold_hmc_wf``)

    **Inputs**

        bold_file
            BOLD series NIfTI file
        raw_ref_image
            Reference image to which BOLD series is motion corrected

    **Outputs**

        xforms
            ITKTransform file aligning each volume to ``ref_image``
        movpar_file
            Head Motion parameters, normalized to SPM format (X, Y, Z, Rx, Ry, Rz)

    """
    if use_mcflirt:
        software = """\
`mcflirt` [FSL {fsl_ver}, @mcflirt].
""".format(fsl_ver=fsl.Info().version() or '<ver>')
    else:
        software = """\
`3dVolreg` from AFNI, version {afni_ver} [@afni, RRID:SCR_005927].
""".format(afni_ver=''.join(list(afni.Volreg().version or '<ver>')))

    workflow = Workflow(name=name)
    workflow.__desc__ = """\
Head-motion parameters with respect to the BOLD reference
(transformation matrices, and six corresponding rotation and translation
parameters) are estimated before any spatiotemporal filtering using
{}.""".format(software)

    inputnode = pe.Node(niu.IdentityInterface(fields=['bold_file', 'raw_ref_image']),
                        name='inputnode')
    outputnode = pe.Node(
        niu.IdentityInterface(fields=['xforms', 'movpar_file']),
        name='outputnode')

    normalize_motion = pe.Node(NormalizeMotionParams(
        format='FSL' if use_mcflirt else 'AFNI'),
        name="normalize_motion", mem_gb=DEFAULT_MEMORY_MIN_GB)

    # Head motion correction (hmc)
    if use_mcflirt:
        mc = pe.Node(fsl.MCFLIRT(save_mats=True, save_plots=True),
                     name='mc', mem_gb=mem_gb * 3)

        mc2itk = pe.Node(MCFLIRT2ITK(), name='mc2itk',
                         mem_gb=0.05, n_procs=omp_nthreads)
        workflow.connect([
            (inputnode, mc, [('raw_ref_image', 'ref_file'),
                             ('bold_file', 'in_file')]),
            (inputnode, mc2itk, [('raw_ref_image', 'in_source'),
                                 ('raw_ref_image', 'in_reference')]),
            (mc, mc2itk, [('mat_file', 'in_files')]),
            (mc, normalize_motion, [('par_file', 'in_file')]),
        ])
    else:
        mc = pe.Node(afni.Volreg(args='-prefix NULL -twopass',
                                 zpad=4, outputtype='NIFTI_GZ'), name="mc", mem_gb=mem_gb * 3)
        mc2itk = pe.Node(Volreg2ITK(), name='mc2itk', mem_gb=0.05)

        workflow.connect([
            (inputnode, mc, [('raw_ref_image', 'basefile'),
                             ('bold_file', 'in_file')]),
            (mc, mc2itk, [('oned_matrix_save', 'in_file')]),
            (mc, normalize_motion, [('oned_file', 'in_file')]),
        ])

    workflow.connect([
        (mc2itk, outputnode, [('out_file', 'xforms')]),
        (normalize_motion, outputnode, [('out_file', 'movpar_file')]),
    ])

    return workflow
