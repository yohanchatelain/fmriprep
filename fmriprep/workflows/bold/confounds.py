# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Calculate BOLD confounds
^^^^^^^^^^^^^^^^^^^^^^^^

.. autofunction:: init_bold_confs_wf
.. autofunction:: init_ica_aroma_wf

"""
from niworkflows.nipype.pipeline import engine as pe
from niworkflows.nipype.interfaces import utility as niu, fsl
from niworkflows.nipype.interfaces.nilearn import SignalExtraction
from niworkflows.nipype.algorithms import confounds as nac

from niworkflows.interfaces import segmentation as nws
from niworkflows.interfaces.masks import ACompCorRPT, TCompCorRPT
from niworkflows.interfaces.fixes import FixHeaderApplyTransforms as ApplyTransforms

from ...interfaces import (
    TPM2ROI, ConcatROIs, CombineROIs, AddTSVHeader, GatherConfounds, ICAConfounds
)


def init_bold_confs_wf(mem_gb, use_aroma, ignore_aroma_err, metadata,
                       name="bold_confs_wf"):
    """
    This workflow calculates confounds for a BOLD series, and aggregates them
    into a :abbr:`TSV (tab-separated value)` file, for use as nuisance
    regressors in a :abbr:`GLM (general linear model)`.

    The following confounds are calculated, with column headings in parentheses:

    #. White matter / global signals (``WhiteMatter``, ``GlobalSignal``)
    #. DVARS - standard, nonstandard, and voxel-wise standard variants
       (``stdDVARS``, ``non-stdDVARS``, ``vx-wisestdDVARS``)
    #. Framewise displacement, based on MCFLIRT motion parameters
       (``FramewiseDisplacement``)
    #. Temporal CompCor (``tCompCorXX``)
    #. Anatomical CompCor (``aCompCorXX``)
    #. Cosine basis set for high-pass filtering w/ 0.008 Hz cut-off
       (``CosineXX``)
    #. Non-steady-state volumes (``NonSteadyStateXX``)
    #. Estimated head-motion parameters, in mm and rad
       (``X``, ``Y``, ``Z``, ``RotX``, ``RotY``, ``RotZ``)
    #. ICA-AROMA-identified noise components, if enabled
       (``AROMAAggrCompXX``)

    Prior to estimating aCompCor and tCompCor, non-steady-state volumes are
    censored and high-pass filtered using a :abbr:`DCT (discrete cosine
    transform)` basis.
    The cosine basis, as well as one regressor per censored volume, are included
    for convenience.

    .. workflow::
        :graph2use: orig
        :simple_form: yes

        from fmriprep.workflows.bold.confounds import init_bold_confs_wf
        wf = init_bold_confs_wf(
            mem_gb=1,
            use_aroma=True,
            ignore_aroma_err=True,
            metadata={})

    **Parameters**

        mem_gb : float
            Size of BOLD file in GB - please note that this size
            should be calculated after resamplings that may extend
            the FoV
        use_aroma : bool
            Perform ICA-AROMA on MNI-resampled functional series
        ignore_aroma_err : bool
            Do not fail on ICA-AROMA errors
        metadata : dict
            BIDS metadata for BOLD file

    **Inputs**

        bold
            BOLD image, after the prescribed corrections (STC, HMC and SDC)
            when available.
        bold_mask
            BOLD series mask
        movpar_file
            SPM-formatted motion parameters file
        t1_mask
            Mask of the skull-stripped template image
        t1_tpms
            List of tissue probability maps in T1w space
        t1_bold_xform
            Affine matrix that maps the T1w space into alignment with
            the native BOLD space
        bold_mni
            BOLD image resampled in MNI space (only if ``use_aroma`` enabled)
        bold_mask_mni
            Brain mask corresponding to the BOLD image resampled in MNI space
            (only if ``use_aroma`` enabled)

    **Outputs**

        confounds_file
            TSV of all aggregated confounds
        confounds_list
            List of calculated confounds for reporting
        acompcor_report
            Reportlet visualizing white-matter/CSF mask used for aCompCor
        tcompcor_report
            Reportlet visualizing ROI identified in tCompCor
        ica_aroma_report
            Reportlet visualizing MELODIC ICs, with ICA-AROMA signal/noise labels
        aroma_noise_ics
            CSV of noise components identified by ICA-AROMA
        melodic_mix
            FSL MELODIC mixing matrix
        nonaggr_denoised_file
            BOLD series with non-aggressive ICA-AROMA denoising applied

    **Subworkflows**

        * :py:func:`~fmriprep.workflows.bold.confounds.init_ica_aroma_wf`

    """

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['bold', 'bold_mask', 'movpar_file', 't1_mask', 't1_tpms',
                't1_bold_xform', 'bold_mni', 'bold_mask_mni']),
        name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['confounds_file', 'confounds_list', 'acompcor_report', 'tcompcor_report',
                'ica_aroma_report', 'aroma_noise_ics', 'melodic_mix',
                'nonaggr_denoised_file']),
        name='outputnode')

    # Map space-T1w objects into BOLD space
    mask_t1w_tfm = pe.Node(
        ApplyTransforms(interpolation='NearestNeighbor', float=True),
        name='mask_t1w_tfm', mem_gb=0.1
    )

    tpms_t1w_tfm = pe.MapNode(ApplyTransforms(float=True),
                              name='tpms_t1w_tfm', mem_gb=0.1,
                              iterfield=['input_image'])

    # DVARS
    dvars = pe.Node(nac.ComputeDVARS(save_all=True, remove_zerovariance=True),
                    name="dvars", mem_gb=mem_gb)

    # Frame displacement
    fdisp = pe.Node(nac.FramewiseDisplacement(parameter_source="SPM"),
                    name="fdisp", mem_gb=mem_gb)

    # CompCor
    non_steady_state = pe.Node(nac.NonSteadyStateDetector(), name='non_steady_state')
    tcompcor = pe.Node(TCompCorRPT(components_file='tcompcor.tsv',
                                   generate_report=True,
                                   pre_filter='cosine',
                                   save_pre_filter=True,
                                   percentile_threshold=.05),
                       name="tcompcor", mem_gb=mem_gb)
    acompcor = pe.Node(ACompCorRPT(components_file='acompcor.tsv',
                                   pre_filter='cosine',
                                   save_pre_filter=True,
                                   generate_report=True),
                       name="acompcor", mem_gb=mem_gb)

    csf_roi = pe.Node(TPM2ROI(erode_mm=0, mask_erode_mm=30), name='csf_roi')
    wm_roi = pe.Node(TPM2ROI(erode_prop=0.6,
                             mask_erode_prop=0.6**3),  # 0.6 = radius; 0.6^3 = volume
                     name='wm_roi')
    merge_rois = pe.Node(niu.Merge(2), name='merge_rois', run_without_submitting=True, mem_gb=0.01)
    combine_rois = pe.Node(CombineROIs(), name='combine_rois')
    concat_rois = pe.Node(ConcatROIs(), name='concat_rois')

    # Global and segment regressors
    signals = pe.Node(SignalExtraction(detrend=True,
                                       class_labels=["WhiteMatter", "GlobalSignal"]),
                      name="signals", mem_gb=mem_gb)

    # Arrange confounds
    add_header = pe.Node(AddTSVHeader(columns=["X", "Y", "Z", "RotX", "RotY", "RotZ"]),
                         name="add_header", mem_gb=0.01, run_without_submitting=True)
    concat = pe.Node(GatherConfounds(), name="concat", mem_gb=0.01, run_without_submitting=True)

    # Set TR if present
    if 'RepetitionTime' in metadata:
        tcompcor.inputs.repetition_time = metadata['RepetitionTime']
        acompcor.inputs.repetition_time = metadata['RepetitionTime']

    def _select(files):
        return [files[0], files[2]]

    def _pick_csf(files):
        return files[0]

    def _pick_wm(files):
        return files[-1]

    workflow = pe.Workflow(name=name)
    workflow.connect([
        (inputnode, mask_t1w_tfm, [('t1_mask', 'input_image'),
                                   ('bold_mask', 'reference_image'),
                                   ('t1_bold_xform', 'transforms')]),
        (inputnode, tpms_t1w_tfm, [(('t1_tpms', _select), 'input_image'),
                                   ('bold_mask', 'reference_image'),
                                   ('t1_bold_xform', 'transforms')]),
        # Massage ROIs
        (inputnode, csf_roi, [('bold_mask', 'bold_mask')]),
        (inputnode, wm_roi, [('bold_mask', 'bold_mask')]),
        (tpms_t1w_tfm, csf_roi, [(('output_image', _pick_csf), 't1_tpm')]),
        (mask_t1w_tfm, csf_roi, [('output_image', 't1_mask')]),
        (tpms_t1w_tfm, wm_roi, [(('output_image', _pick_wm), 't1_tpm')]),
        (mask_t1w_tfm, wm_roi, [('output_image', 't1_mask')]),

        # connect inputnode to each non-anatomical confound node
        (inputnode, dvars, [('bold', 'in_file'),
                            ('bold_mask', 'in_mask')]),
        (inputnode, fdisp, [('movpar_file', 'in_file')]),

        # Calculate nonsteady state
        (inputnode, non_steady_state, [('bold', 'in_file')]),

        # tCompCor
        (inputnode, tcompcor, [('bold', 'realigned_file')]),
        (non_steady_state, tcompcor, [('n_volumes_to_discard', 'ignore_initial_volumes')]),
        (csf_roi, tcompcor, [('eroded_mask', 'mask_files')]),

        # aCompCor
        (inputnode, acompcor, [('bold', 'realigned_file')]),
        (non_steady_state, acompcor, [('n_volumes_to_discard', 'ignore_initial_volumes')]),
        (inputnode, combine_rois, [('bold', 'ref_header')]),
        (merge_rois, combine_rois, [('out', 'in_files')]),
        (combine_rois, acompcor, [('out_file', 'mask_files')]),

        (csf_roi, merge_rois, [('roi_file', 'in1')]),
        (wm_roi, merge_rois, [('roi_file', 'in2')]),

        # Global signal extraction (constrained by anatomy)
        (inputnode, signals, [('bold', 'in_file')]),
        (inputnode, concat_rois, [('bold', 'ref_header'),
                                  ('bold_mask', 'in_mask')]),
        (wm_roi, concat_rois, [('roi_file', 'in_file')]),
        (concat_rois, signals, [('out_file', 'label_files')]),

        # Collate computed confounds together
        (inputnode, add_header, [('movpar_file', 'in_file')]),
        (signals, concat, [('out_file', 'signals')]),
        (dvars, concat, [('out_all', 'dvars')]),
        (fdisp, concat, [('out_file', 'fd')]),
        (tcompcor, concat, [('components_file', 'tcompcor'),
                            ('pre_filter_file', 'cos_basis')]),
        (acompcor, concat, [('components_file', 'acompcor')]),
        (add_header, concat, [('out_file', 'motion')]),

        # Set outputs
        (concat, outputnode, [('confounds_file', 'confounds_file'),
                              ('confounds_list', 'confounds_list')]),
        (acompcor, outputnode, [('out_report', 'acompcor_report')]),
        (tcompcor, outputnode, [('out_report', 'tcompcor_report')]),
    ])

    if use_aroma:
        # ICA-AROMA
        ica_aroma_wf = init_ica_aroma_wf(name='ica_aroma_wf',
                                         ignore_aroma_err=ignore_aroma_err)
        workflow.connect([
            (inputnode, ica_aroma_wf, [('bold_mni', 'inputnode.bold_mni'),
                                       ('bold_mask_mni', 'inputnode.bold_mask_mni'),
                                       ('movpar_file', 'inputnode.movpar_file')]),
            (ica_aroma_wf, concat,
                [('outputnode.aroma_confounds', 'aroma')]),
            (ica_aroma_wf, outputnode,
                [('outputnode.out_report', 'ica_aroma_report'),
                 ('outputnode.aroma_noise_ics', 'aroma_noise_ics'),
                 ('outputnode.melodic_mix', 'melodic_mix'),
                 ('outputnode.nonaggr_denoised_file', 'nonaggr_denoised_file')])
        ])
    return workflow


def init_ica_aroma_wf(name='ica_aroma_wf', ignore_aroma_err=False):
    '''
    This workflow wraps `ICA-AROMA`_ to identify and remove motion-related
    independent components from a BOLD time series.

    The following steps are performed:

    #. Smooth data using SUSAN
    #. Run MELODIC outside of ICA-AROMA to generate the report
    #. Run ICA-AROMA
    #. Aggregate identified motion components (aggressive) to TSV
    #. Return classified_motion_ICs and melodic_mix for user to complete
        non-aggressive denoising in T1w space

    Additionally, non-aggressive denoising is performed on the BOLD series
    resampled into MNI space.

    .. workflow::
        :graph2use: orig
        :simple_form: yes

        from fmriprep.workflows.bold.confounds import init_ica_aroma_wf
        wf = init_ica_aroma_wf()

    **Parameters**

        ignore_aroma_err : bool
            Do not fail on ICA-AROMA errors

    **Inputs**

        bold_mni
            BOLD series, resampled to template space
        movpar_file
            SPM-formatted motion parameters file
        bold_mask_mni
            BOLD series mask in template space

    **Outputs**

        aroma_confounds
            TSV of confounds identified as noise by ICA-AROMA
        aroma_noise_ics
            CSV of noise components identified by ICA-AROMA
        melodic_mix
            FSL MELODIC mixing matrix
        nonaggr_denoised_file
            BOLD series with non-aggressive ICA-AROMA denoising applied
        out_report
            Reportlet visualizing MELODIC ICs, with ICA-AROMA signal/noise labels

    .. _ICA-AROMA: https://github.com/rhr-pruim/ICA-AROMA
    '''
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['bold_mni', 'movpar_file', 'bold_mask_mni']), name='inputnode')

    outputnode = pe.Node(niu.IdentityInterface(
        fields=['aroma_confounds', 'out_report',
                'aroma_noise_ics', 'melodic_mix',
                'nonaggr_denoised_file']), name='outputnode')

    calc_median_val = pe.Node(fsl.ImageStats(op_string='-k %s -p 50'), name='calc_median_val')
    calc_bold_mean = pe.Node(fsl.MeanImage(), name='calc_bold_mean')

    def getusans_func(image, thresh):
        return [tuple([image, thresh])]
    getusans = pe.Node(niu.Function(function=getusans_func, output_names=['usans']),
                       name='getusans', mem_gb=0.01)

    smooth = pe.Node(fsl.SUSAN(fwhm=6.0), name='smooth')

    # melodic node
    melodic = pe.Node(fsl.MELODIC(no_bet=True, no_mm=True), name="melodic")

    # ica_aroma node
    ica_aroma = pe.Node(nws.ICA_AROMARPT(denoise_type='nonaggr', generate_report=True),
                        name='ica_aroma')

    # extract the confound ICs from the results
    ica_aroma_confound_extraction = pe.Node(ICAConfounds(ignore_aroma_err=ignore_aroma_err),
                                            name='ica_aroma_confound_extraction')

    def _getbtthresh(medianval):
        return 0.75 * medianval

    # connect the nodes
    workflow.connect([
        # Connect input nodes to complete smoothing
        (inputnode, calc_median_val, [('bold_mni', 'in_file'),
                                      ('bold_mask_mni', 'mask_file')]),
        (inputnode, calc_bold_mean, [('bold_mni', 'in_file')]),
        (calc_bold_mean, getusans, [('out_file', 'image')]),
        (calc_median_val, getusans, [('out_stat', 'thresh')]),
        (inputnode, smooth, [('bold_mni', 'in_file')]),
        (getusans, smooth, [('usans', 'usans')]),
        (calc_median_val, smooth, [(('out_stat', _getbtthresh), 'brightness_threshold')]),
        # connect smooth to melodic
        (smooth, melodic, [('smoothed_file', 'in_files')]),
        (inputnode, melodic, [('bold_mask_mni', 'mask')]),
        # connect nodes to ICA-AROMA
        (smooth, ica_aroma, [('smoothed_file', 'in_file')]),
        (inputnode, ica_aroma, [('bold_mask_mni', 'report_mask'),
                                ('movpar_file', 'motion_parameters')]),
        (melodic, ica_aroma, [('out_dir', 'melodic_dir')]),
        # generate tsvs from ICA-AROMA
        (ica_aroma, ica_aroma_confound_extraction, [('out_dir', 'in_directory')]),
        # output for processing and reporting
        (ica_aroma_confound_extraction, outputnode, [('aroma_confounds', 'aroma_confounds'),
                                                     ('aroma_noise_ics', 'aroma_noise_ics'),
                                                     ('melodic_mix', 'melodic_mix')]),
        # TODO change melodic report to reflect noise and non-noise components
        (ica_aroma, outputnode, [('out_report', 'out_report'),
                                 ('nonaggr_denoised_file', 'nonaggr_denoised_file')]),
    ])

    return workflow
