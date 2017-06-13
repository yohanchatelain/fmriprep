#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Anatomical Reference -processing workflows.

Originally coded by Craig Moodie. Refactored by the CRN Developers.

"""
from __future__ import print_function, division, absolute_import, unicode_literals

import os.path as op

from niworkflows.nipype.interfaces import ants
from niworkflows.nipype.interfaces import freesurfer as fs
from niworkflows.nipype.interfaces import utility as niu
from niworkflows.nipype.interfaces import io as nio
from niworkflows.nipype.pipeline import engine as pe

from niworkflows.interfaces.registration import RobustMNINormalizationRPT
from niworkflows.anat.skullstrip import afni_wf as init_skullstrip_afni_wf
import niworkflows.data as nid
from niworkflows.interfaces.masks import BrainExtractionRPT
from niworkflows.interfaces.segmentation import FASTRPT, ReconAllRPT

from fmriprep.interfaces import DerivativesDataSink, StructuralReference, MakeMidthickness
from fmriprep.interfaces.images import reorient
from fmriprep.utils.misc import fix_multi_T1w_source_name, add_suffix


#  pylint: disable=R0914
def init_anat_preproc_wf(skull_strip_ants, output_spaces, template, debug, freesurfer,
                         omp_nthreads, hires, reportlets_dir, output_dir,
                         name='anat_preproc_wf'):
    """T1w images preprocessing pipeline"""

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(fields=['t1w', 't2w', 'subjects_dir']),
        name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['t1_preproc', 't1_brain', 't1_mask', 't1_seg', 't1_tpms',
                't1_2_mni', 't1_2_mni_forward_transform', 't1_2_mni_reverse_transform',
                'mni_mask', 'mni_tpms',
                'subjects_dir', 'subject_id', 'fs_2_t1_transform', 'surfaces']),
        name='outputnode')

    # 0. Align and merge if several T1w images are provided
    t1_merge = pe.Node(
        # StructuralReference is fs.RobustTemplate if > 1 volume, copying otherwise
        StructuralReference(auto_detect_sensitivity=True,
                            initial_timepoint=1,
                            fixed_timepoint=True,     # Align to first image
                            intensity_scaling=True,   # 7-DOF (rigid + intensity)
                            no_iteration=True,
                            subsample_threshold=200,
                            ), name='t1_merge')

    # 1. Reorient T1
    t1_conform = pe.Node(niu.Function(function=reorient), name='t1_conform')

    # 2. T1 Bias Field Correction
    # Bias field correction is handled in skull strip workflows.

    # 3. Skull-stripping
    skullstrip_wf = init_skullstrip_afni_wf(name='skullstrip_afni_wf')
    if skull_strip_ants:
        skullstrip_wf = init_skullstrip_ants_wf(name='skullstrip_ants_wf',
                                                debug=debug,
                                                omp_nthreads=omp_nthreads)

    # 4. Segmentation
    t1_seg = pe.Node(FASTRPT(generate_report=True, segments=True,
                             no_bias=True, probability_maps=True),
                     name='t1_seg')

    # 5. Spatial normalization (T1w to MNI registration)
    t1_2_mni = pe.Node(
        RobustMNINormalizationRPT(
            generate_report=True,
            num_threads=omp_nthreads,
            flavor='testing' if debug else 'precise',
        ),
        name='t1_2_mni'
    )
    # should not be necesssary but does not hurt - make sure the multiproc
    # scheduler knows the resource limits
    t1_2_mni.interface.num_threads = omp_nthreads

    # Resample the brain mask and the tissue probability maps into mni space
    mni_mask = pe.Node(
        ants.ApplyTransforms(dimension=3, default_value=0, float=True,
                             interpolation='NearestNeighbor'),
        name='mni_mask'
    )

    mni_tpms = pe.MapNode(
        ants.ApplyTransforms(dimension=3, default_value=0, float=True,
                             interpolation='Linear'),
        iterfield=['input_image'],
        name='mni_tpms'
    )

    workflow.connect([
        (inputnode, t1_merge, [('t1w', 'in_files'),
                               (('t1w', add_suffix, '_template'), 'out_file')]),
        (t1_merge, t1_conform, [('out_file', 'in_file')]),
        (t1_conform, skullstrip_wf, [('out', 'inputnode.in_file')]),
        (skullstrip_wf, t1_seg, [('outputnode.out_file', 'in_files')]),
        (skullstrip_wf, outputnode, [('outputnode.bias_corrected', 't1_preproc'),
                                     ('outputnode.out_file', 't1_brain'),
                                     ('outputnode.out_mask', 't1_mask')]),
        (t1_seg, outputnode, [('tissue_class_map', 't1_seg'),
                              ('probability_maps', 't1_tpms')]),
        ])
    if 'template' in output_spaces:
        template_str = nid.TEMPLATE_MAP[template]
        ref_img = op.join(nid.get_dataset(template_str), '1mm_T1.nii.gz')

        t1_2_mni.inputs.template = template_str
        mni_mask.inputs.reference_image = ref_img
        mni_tpms.inputs.reference_image = ref_img

        workflow.connect([
            (skullstrip_wf, t1_2_mni, [('outputnode.bias_corrected', 'moving_image')]),
            (skullstrip_wf, t1_2_mni, [('outputnode.out_mask', 'moving_mask')]),
            (skullstrip_wf, mni_mask, [('outputnode.out_mask', 'input_image')]),
            (t1_2_mni, mni_mask, [('composite_transform', 'transforms')]),
            (t1_seg, mni_tpms, [('probability_maps', 'input_image')]),
            (t1_2_mni, mni_tpms, [('composite_transform', 'transforms')]),
            (t1_2_mni, outputnode, [
                ('warped_image', 't1_2_mni'),
                ('composite_transform', 't1_2_mni_forward_transform'),
                ('inverse_composite_transform', 't1_2_mni_reverse_transform')]),
            (mni_mask, outputnode, [('output_image', 'mni_mask')]),
            (mni_tpms, outputnode, [('output_image', 'mni_tpms')]),
        ])

    # 6. FreeSurfer reconstruction
    if freesurfer:
        surface_recon_wf = init_surface_recon_wf(name='surface_recon_wf',
                                                 omp_nthreads=omp_nthreads, hires=hires)

        workflow.connect([
            (inputnode, surface_recon_wf, [
                ('t2w', 'inputnode.t2w'),
                ('subjects_dir', 'inputnode.subjects_dir')]),
            (t1_conform, surface_recon_wf, [('out', 'inputnode.t1w')]),
            (skullstrip_wf, surface_recon_wf, [
                ('outputnode.out_file', 'inputnode.skullstripped_t1')]),
            (surface_recon_wf, outputnode, [
                ('outputnode.subjects_dir', 'subjects_dir'),
                ('outputnode.subject_id', 'subject_id'),
                ('outputnode.fs_2_t1_transform', 'fs_2_t1_transform'),
                ('outputnode.surfaces', 'surfaces')]),
            ])

    anat_reports_wf = init_anat_reports_wf(
        reportlets_dir=reportlets_dir, skull_strip_ants=skull_strip_ants,
        output_spaces=output_spaces, template=template, freesurfer=freesurfer)
    workflow.connect([
        (inputnode, anat_reports_wf, [
            (('t1w', fix_multi_T1w_source_name), 'inputnode.source_file')]),
        (t1_seg, anat_reports_wf, [('out_report', 'inputnode.t1_seg_report')]),
        ])

    if skull_strip_ants:
        workflow.connect([
            (skullstrip_wf, anat_reports_wf, [
                ('outputnode.out_report', 'inputnode.t1_skull_strip_report')])
        ])
    if freesurfer:
        workflow.connect([
            (surface_recon_wf, anat_reports_wf, [
                ('outputnode.out_report', 'inputnode.recon_report')])
        ])
    if 'template' in output_spaces:
        workflow.connect([
            (t1_2_mni, anat_reports_wf, [('out_report', 'inputnode.t1_2_mni_report')]),
        ])

    anat_derivatives_wf = init_anat_derivatives_wf(output_dir=output_dir,
                                                   output_spaces=output_spaces,
                                                   template=template,
                                                   freesurfer=freesurfer)

    workflow.connect([
        (inputnode, anat_derivatives_wf, [
            (('t1w', fix_multi_T1w_source_name), 'inputnode.source_file')]),
        (outputnode, anat_derivatives_wf, [
            ('t1_preproc', 'inputnode.t1_preproc'),
            ('t1_mask', 'inputnode.t1_mask'),
            ('t1_seg', 'inputnode.t1_seg'),
            ('t1_2_mni_forward_transform', 'inputnode.t1_2_mni_forward_transform'),
            ('t1_2_mni', 'inputnode.t1_2_mni'),
            ('mni_mask', 'inputnode.mni_mask'),
            ('mni_tpms', 'inputnode.mni_tpms'),
            ('surfaces', 'inputnode.surfaces'),
            ]),
        ])

    return workflow


def init_skullstrip_ants_wf(debug, omp_nthreads, name='skullstrip_ants_wf'):
    from niworkflows.data import get_ants_oasis_template_ras

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=['in_file', 'source_file']),
                        name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(
        fields=['bias_corrected', 'out_file', 'out_mask', 'out_report']), name='outputnode')

    t1_skull_strip = pe.Node(BrainExtractionRPT(
        dimension=3, use_floatingpoint_precision=1,
        debug=debug, generate_report=True,
        num_threads=omp_nthreads, keep_temporary_files=1),
        name='t1_skull_strip')

    # should not be necesssary byt does not hurt - make sure the multiproc
    # scheduler knows the resource limits
    t1_skull_strip.interface.num_threads = omp_nthreads

    t1_skull_strip.inputs.brain_template = op.join(
        get_ants_oasis_template_ras(),
        'T_template0.nii.gz'
    )
    t1_skull_strip.inputs.brain_probability_mask = op.join(
        get_ants_oasis_template_ras(),
        'T_template0_BrainCerebellumProbabilityMask.nii.gz'
    )
    t1_skull_strip.inputs.extraction_registration_mask = op.join(
        get_ants_oasis_template_ras(),
        'T_template0_BrainCerebellumRegistrationMask.nii.gz'
    )

    workflow.connect([
        (inputnode, t1_skull_strip, [('in_file', 'anatomical_image')]),
        (t1_skull_strip, outputnode, [('BrainExtractionMask', 'out_mask'),
                                      ('BrainExtractionBrain', 'out_file'),
                                      ('N4Corrected0', 'bias_corrected'),
                                      ('out_report', 'out_report')])
    ])

    return workflow


def init_surface_recon_wf(omp_nthreads, hires, name='surface_recon_wf'):

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=['t1w', 't2w', 'skullstripped_t1', 'subjects_dir']),
        name='inputnode')
    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=['subjects_dir', 'subject_id', 'fs_2_t1_transform', 'surfaces', 'out_report']),
        name='outputnode')

    def detect_inputs(t1w_list, t2w_list=[], hires_enabled=True):
        from niworkflows.nipype.interfaces.base import isdefined
        from niworkflows.nipype.utils.filemanip import filename_to_list
        from niworkflows.nipype.interfaces.traits_extension import Undefined
        import nibabel as nib
        t1w_list = filename_to_list(t1w_list)
        t2w_list = filename_to_list(t2w_list) if isdefined(t2w_list) else []
        t1w_ref = nib.load(t1w_list[0])
        # Use high resolution preprocessing if voxel size < 1.0mm
        # Tolerance of 0.05mm requires that rounds down to 0.9mm or lower
        hires = hires_enabled and max(t1w_ref.header.get_zooms()) < 1 - 0.05

        t2w = Undefined
        if t2w_list and max(nib.load(t2w_list[0]).header.get_zooms()) < 1.2:
            t2w = t2w_list[0]

        # https://surfer.nmr.mgh.harvard.edu/fswiki/SubmillimeterRecon
        mris_inflate = '-n 50' if hires else Undefined
        return (t2w, isdefined(t2w), hires, mris_inflate)

    recon_config = pe.Node(
        niu.Function(
            function=detect_inputs,
            output_names=['t2w', 'use_T2', 'hires', 'mris_inflate']),
        name='recon_config')
    recon_config.inputs.hires_enabled = hires

    def bidsinfo(in_file):
        from fmriprep.interfaces.bids import BIDS_NAME
        match = BIDS_NAME.search(in_file)
        params = match.groupdict() if match is not None else {}
        return tuple(map(params.get, ['subject_id', 'ses_id', 'task_id',
                                      'acq_id', 'rec_id', 'run_id']))

    bids_info = pe.Node(
        niu.Function(function=bidsinfo,
                     output_names=['subject_id', 'ses_id', 'task_id',
                                   'acq_id', 'rec_id', 'run_id']),
        name='bids_info',
        run_without_submitting=True)

    autorecon1 = pe.Node(
        fs.ReconAll(
            directive='autorecon1',
            flags='-noskullstrip',
            openmp=omp_nthreads),
        name='autorecon1')
    autorecon1.interface._can_resume = False
    autorecon1.interface.num_threads = omp_nthreads

    def inject_skullstripped(subjects_dir, subject_id, skullstripped):
        import os
        import nibabel as nib
        from nilearn.image import resample_to_img, new_img_like
        from niworkflows.nipype.utils.filemanip import copyfile
        mridir = os.path.join(subjects_dir, subject_id, 'mri')
        t1 = os.path.join(mridir, 'T1.mgz')
        bm_auto = os.path.join(mridir, 'brainmask.auto.mgz')
        bm = os.path.join(mridir, 'brainmask.mgz')

        if not os.path.exists(bm_auto):
            img = nib.load(t1)
            mask = nib.load(skullstripped)
            bmask = new_img_like(mask, mask.get_data() > 0)
            resampled_mask = resample_to_img(bmask, img, 'nearest')
            masked_image = new_img_like(img, img.get_data() * resampled_mask.get_data())
            masked_image.to_filename(bm_auto)

        if not os.path.exists(bm):
            copyfile(bm_auto, bm, copy=True, use_hardlink=True)

        return subjects_dir, subject_id

    skull_strip_extern = pe.Node(
        niu.Function(function=inject_skullstripped,
                     output_names=['subjects_dir', 'subject_id']),
        name='skull_strip_extern')

    fs_transform = pe.Node(
        fs.Tkregister2(fsl_out='freesurfer2subT1.mat', reg_header=True),
        name='fs_transform')

    autorecon_resume_wf = init_autorecon_resume_wf(omp_nthreads=omp_nthreads)
    gifti_surface_wf = init_gifti_surface_wf()

    workflow.connect([
        # Configuration
        (inputnode, recon_config, [('t1w', 't1w_list'),
                                   ('t2w', 't2w_list')]),
        (inputnode, bids_info, [(('t1w', fix_multi_T1w_source_name), 'in_file')]),
        # Passing subjects_dir / subject_id enforces serial order
        (inputnode, autorecon1, [('subjects_dir', 'subjects_dir')]),
        (bids_info, autorecon1, [('subject_id', 'subject_id')]),
        (autorecon1, skull_strip_extern, [('subjects_dir', 'subjects_dir'),
                                          ('subject_id', 'subject_id')]),
        (skull_strip_extern, autorecon_resume_wf, [('subjects_dir', 'inputnode.subjects_dir'),
                                                   ('subject_id', 'inputnode.subject_id')]),
        (autorecon_resume_wf, gifti_surface_wf, [
            ('outputnode.subjects_dir', 'inputnode.subjects_dir'),
            ('outputnode.subject_id', 'inputnode.subject_id')]),
        # Reconstruction phases
        (inputnode, autorecon1, [('t1w', 'T1_files')]),
        (recon_config, autorecon1, [('t2w', 'T2_file'),
                                    ('hires', 'hires'),
                                    # First run only (recon-all saves expert options)
                                    ('mris_inflate', 'mris_inflate')]),
        (inputnode, skull_strip_extern, [('skullstripped_t1', 'skullstripped')]),
        (recon_config, autorecon_resume_wf, [('use_T2', 'inputnode.use_T2')]),
        # Construct transform from FreeSurfer conformed image to FMRIPREP
        # reoriented image
        (inputnode, fs_transform, [('t1w', 'target_image')]),
        (autorecon1, fs_transform, [('T1', 'moving_image')]),
        # Output
        (autorecon_resume_wf, outputnode, [('outputnode.subjects_dir', 'subjects_dir'),
                                           ('outputnode.subject_id', 'subject_id'),
                                           ('outputnode.out_report', 'out_report')]),
        (gifti_surface_wf, outputnode, [('outputnode.surfaces', 'surfaces')]),
        (fs_transform, outputnode, [('fsl_file', 'fs_2_t1_transform')]),
        ])

    return workflow


def init_autorecon_resume_wf(omp_nthreads, name='autorecon_resume_wf'):
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=['subjects_dir', 'subject_id', 'use_T2']),
        name='inputnode')

    outputnode = pe.Node(
        niu.IdentityInterface(
            fields=['subjects_dir', 'subject_id', 'out_report']),
        name='outputnode')

    autorecon2_vol = pe.Node(
        fs.ReconAll(
            directive='autorecon2-volonly',
            openmp=omp_nthreads),
        name='autorecon2_vol')
    autorecon2_vol.interface.num_threads = omp_nthreads

    autorecon2_surfs = pe.MapNode(
        fs.ReconAll(
            directive='autorecon2-perhemi',
            openmp=omp_nthreads),
        iterfield='hemi',
        name='autorecon2_surfs')
    autorecon2_surfs.interface.num_threads = omp_nthreads
    autorecon2_surfs.inputs.hemi = ['lh', 'rh']

    autorecon_surfs = pe.MapNode(
        fs.ReconAll(
            directive='autorecon-hemi',
            flags=['-noparcstats', '-noparcstats2', '-noparcstats3',
                   '-nohyporelabel', '-nobalabels'],
            openmp=omp_nthreads),
        iterfield='hemi',
        name='autorecon_surfs')
    autorecon_surfs.interface.num_threads = omp_nthreads
    autorecon_surfs.inputs.hemi = ['lh', 'rh']

    autorecon3 = pe.Node(
        ReconAllRPT(
            directive='autorecon3',
            openmp=omp_nthreads,
            generate_report=True),
        name='autorecon3')
    autorecon3.interface.num_threads = omp_nthreads

    def _dedup(in_list):
        vals = set(in_list)
        if len(vals) > 1:
            raise ValueError(
                "Non-identical values can't be deduplicated:\n{!r}".format(in_list))
        return vals.pop()

    workflow.connect([
        (inputnode, autorecon_surfs, [('use_T2', 'use_T2')]),
        (inputnode, autorecon2_vol, [('subjects_dir', 'subjects_dir'),
                                     ('subject_id', 'subject_id')]),
        (autorecon2_vol, autorecon2_surfs, [('subjects_dir', 'subjects_dir'),
                                            ('subject_id', 'subject_id')]),
        (autorecon2_surfs, autorecon_surfs, [(('subjects_dir', _dedup), 'subjects_dir'),
                                             (('subject_id', _dedup), 'subject_id')]),
        (autorecon_surfs, autorecon3, [(('subjects_dir', _dedup), 'subjects_dir'),
                                       (('subject_id', _dedup), 'subject_id')]),
        (autorecon3, outputnode, [('subjects_dir', 'subjects_dir'),
                                  ('subject_id', 'subject_id'),
                                  ('out_report', 'out_report')]),
        ])

    return workflow


def init_gifti_surface_wf(name='gifti_surface_wf'):
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(['subjects_dir', 'subject_id']), name='inputnode')
    outputnode = pe.Node(niu.IdentityInterface(['surfaces']), name='outputnode')

    get_surfaces = pe.Node(nio.FreeSurferSource(), name='get_surfaces')

    midthickness = pe.MapNode(
        MakeMidthickness(thickness=True, distance=0.5, out_name='midthickness'),
        iterfield='in_file',
        name='midthickness')

    save_midthickness = pe.Node(nio.DataSink(parameterization=False),
                                name='save_midthickness')

    surface_list = pe.Node(niu.Merge(4, ravel_inputs=True),
                           name='surface_list', run_without_submitting=True)
    fs_2_gii = pe.MapNode(fs.MRIsConvert(out_datatype='gii'),
                          iterfield='in_file', name='fs_2_gii')

    def normalize_surfs(in_file):
        """ Re-center GIFTI coordinates to fit align to native T1 space

        For midthickness surfaces, add MidThickness metadata

        Coordinate update based on:
        https://github.com/Washington-University/workbench/blob/1b79e56/src/Algorithms/AlgorithmSurfaceApplyAffine.cxx#L73-L91
        and
        https://github.com/Washington-University/Pipelines/blob/ae69b9a/PostFreeSurfer/scripts/FreeSurfer2CaretConvertAndRegisterNonlinear.sh#L147
        """
        import os
        import numpy as np
        import nibabel as nib
        img = nib.load(in_file)
        pointset = img.get_arrays_from_intent('NIFTI_INTENT_POINTSET')[0]
        coords = pointset.data
        c_ras_keys = ('VolGeomC_R', 'VolGeomC_A', 'VolGeomC_S')
        ras = np.array([float(pointset.metadata[key])
                        for key in c_ras_keys])
        # Apply C_RAS translation to coordinates
        pointset.data = (coords + ras).astype(coords.dtype)

        secondary = nib.gifti.GiftiNVPairs('AnatomicalStructureSecondary',
                                           'MidThickness')
        geom_type = nib.gifti.GiftiNVPairs('GeometricType', 'Anatomical')
        has_ass = has_geo = False
        for nvpair in pointset.meta.data:
            # Remove C_RAS translation from metadata to avoid double-dipping in FreeSurfer
            if nvpair.name in c_ras_keys:
                nvpair.value = '0.000000'
            # Check for missing metadata
            elif nvpair.name == secondary.name:
                has_ass = True
            elif nvpair.name == geom_type.name:
                has_geo = True
        fname = os.path.basename(in_file)
        # Update metadata for MidThickness/graymid surfaces
        if 'midthickness' in fname.lower() or 'graymid' in fname.lower():
            if not has_ass:
                pointset.meta.data.insert(1, secondary)
            if not has_geo:
                pointset.meta.data.insert(2, geom_type)
        img.to_filename(fname)
        return os.path.abspath(fname)

    fix_surfs = pe.MapNode(
        niu.Function(function=normalize_surfs),
        iterfield='in_file',
        name='fix_surfs')

    workflow.connect([
        (inputnode, get_surfaces, [('subjects_dir', 'subjects_dir'),
                                   ('subject_id', 'subject_id')]),
        (inputnode, save_midthickness, [('subjects_dir', 'base_directory'),
                                        ('subject_id', 'container')]),
        # Generate midthickness surfaces and save to FreeSurfer derivatives
        (get_surfaces, midthickness, [('smoothwm', 'in_file'),
                                      ('graymid', 'graymid')]),
        (midthickness, save_midthickness, [('out_file', 'surf.@graymid')]),
        # Produce valid GIFTI surface files (dense mesh)
        (get_surfaces, surface_list, [('smoothwm', 'in1'),
                                      ('pial', 'in2'),
                                      ('inflated', 'in3')]),
        (save_midthickness, surface_list, [('out_file', 'in4')]),
        (surface_list, fs_2_gii, [('out', 'in_file')]),
        (fs_2_gii, fix_surfs, [('converted', 'in_file')]),
        (fix_surfs, outputnode, [('out', 'surfaces')]),
        ])

    return workflow


def init_anat_reports_wf(reportlets_dir, skull_strip_ants, output_spaces,
                         template, freesurfer, name='anat_reports_wf'):
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=['source_file', 't1_seg_report', 't1_2_mni_report',
                    't1_skull_strip_report', 'recon_report']),
        name='inputnode')

    ds_t1_seg_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, suffix='t1_seg'),
        name='ds_t1_seg_report', run_without_submitting=True)

    ds_t1_2_mni_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, suffix='t1_2_mni'),
        name='ds_t1_2_mni_report', run_without_submitting=True)

    ds_t1_skull_strip_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, suffix='t1_skull_strip'),
        name='ds_t1_skull_strip_report', run_without_submitting=True)

    ds_recon_report = pe.Node(
        DerivativesDataSink(base_directory=reportlets_dir, suffix='reconall'),
        name='ds_recon_report', run_without_submitting=True)

    workflow.connect([
        (inputnode, ds_t1_seg_report, [('source_file', 'source_file'),
                                       ('t1_seg_report', 'in_file')]),
    ])

    if skull_strip_ants:
        workflow.connect([
            (inputnode, ds_t1_skull_strip_report, [('source_file', 'source_file'),
                                                   ('t1_skull_strip_report', 'in_file')])
        ])
    if freesurfer:
        workflow.connect([
            (inputnode, ds_recon_report, [('source_file', 'source_file'),
                                          ('recon_report', 'in_file')])
        ])
    if 'template' in output_spaces:
        workflow.connect([
            (inputnode, ds_t1_2_mni_report, [('source_file', 'source_file'),
                                             ('t1_2_mni_report', 'in_file')])
        ])

    return workflow


def init_anat_derivatives_wf(output_dir, output_spaces, template, freesurfer,
                             name='anat_derivatives_wf'):
    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        niu.IdentityInterface(
            fields=['source_file', 't1_preproc', 't1_mask', 't1_seg',
                    't1_2_mni_forward_transform', 't1_2_mni', 'mni_mask',
                    'mni_tpms', 'surfaces']),
        name='inputnode')

    ds_t1_preproc = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='preproc'),
        name='ds_t1_preproc', run_without_submitting=True)

    ds_t1_seg = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='dtissue'),
        name='ds_t1_seg', run_without_submitting=True)

    ds_t1_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix='brainmask'),
        name='ds_t1_mask', run_without_submitting=True)

    suffix_fmt = 'space-{}_{}'.format
    ds_t1_mni = pe.Node(
        DerivativesDataSink(base_directory=output_dir,
                            suffix=suffix_fmt(template, 'preproc')),
        name='ds_t1_mni', run_without_submitting=True)

    ds_mni_mask = pe.Node(
        DerivativesDataSink(base_directory=output_dir,
                            suffix=suffix_fmt(template, 'brainmask')),
        name='ds_mni_mask', run_without_submitting=True)

    ds_mni_tpms = pe.Node(
        DerivativesDataSink(base_directory=output_dir,
                            suffix=suffix_fmt(template, 'class-{extra_value}_probtissue')),
        name='ds_mni_tpms', run_without_submitting=True)
    ds_mni_tpms.inputs.extra_values = ['CSF', 'GM', 'WM']

    ds_t1_mni_warp = pe.Node(
        DerivativesDataSink(base_directory=output_dir, suffix=suffix_fmt(template, 'warp')),
        name='ds_t1_mni_warp', run_without_submitting=True)

    def get_gifti_name(in_file):
        import os
        import re
        in_format = re.compile(r'(?P<LR>[lr])h.(?P<surf>.+)_converted.gii')
        name = os.path.basename(in_file)
        info = in_format.match(name).groupdict()
        info['LR'] = info['LR'].upper()
        return '{surf}.{LR}.surf'.format(**info)

    name_surfs = pe.MapNode(niu.Function(function=get_gifti_name),
                            iterfield='in_file', name='name_surfs')

    ds_surfs = pe.MapNode(
        DerivativesDataSink(base_directory=output_dir),
        iterfield=['in_file', 'suffix'], name='ds_surfs', run_without_submitting=True)

    workflow.connect([
        (inputnode, ds_t1_preproc, [('source_file', 'source_file'),
                                    ('t1_preproc', 'in_file')]),
        (inputnode, ds_t1_mask, [('source_file', 'source_file'),
                                 ('t1_mask', 'in_file')]),
        (inputnode, ds_t1_seg, [('source_file', 'source_file'),
                                ('t1_seg', 'in_file')]),
        ])

    if freesurfer:
        workflow.connect([
            (inputnode, name_surfs, [('surfaces', 'in_file')]),
            (inputnode, ds_surfs, [('source_file', 'source_file'),
                                   ('surfaces', 'in_file')]),
            (name_surfs, ds_surfs, [('out', 'suffix')]),
            ])
    if 'template' in output_spaces:
        workflow.connect([
            (inputnode, ds_t1_mni_warp, [('source_file', 'source_file'),
                                         ('t1_2_mni_forward_transform', 'in_file')]),
            (inputnode, ds_t1_mni, [('source_file', 'source_file'),
                                    ('t1_2_mni', 'in_file')]),
            (inputnode, ds_mni_mask, [('source_file', 'source_file'),
                                      ('mni_mask', 'in_file')]),
            (inputnode, ds_mni_tpms, [('source_file', 'source_file'),
                                      ('mni_tpms', 'in_file')]),
            ])

    return workflow
