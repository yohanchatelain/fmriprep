#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Image tools interfaces
~~~~~~~~~~~~~~~~~~~~~~


"""
import nibabel as nb
from nilearn.masking import compute_epi_mask
from nilearn.image import concat_imgs

from niworkflows.nipype import logging
from niworkflows.nipype.utils.filemanip import fname_presuffix
from niworkflows.nipype.interfaces.base import (
    traits, isdefined, TraitedSpec, BaseInterfaceInputSpec,
    File, InputMultiPath, SimpleInterface
)

LOGGER = logging.getLogger('interface')


class MaskEPIInputSpec(BaseInterfaceInputSpec):
    in_files = InputMultiPath(File(exists=True), mandatory=True,
                              desc='input EPI or list of files')
    lower_cutoff = traits.Float(0.2, usedefault=True)
    upper_cutoff = traits.Float(0.85, usedefault=True)
    connected = traits.Bool(True, usedefault=True)
    opening = traits.Int(2, usedefault=True)
    exclude_zeros = traits.Bool(False, usedefault=True)
    ensure_finite = traits.Bool(True, usedefault=True)
    target_affine = traits.Either(None, traits.File(exists=True),
                                  default=None, usedefault=True)
    target_shape = traits.Either(None, traits.File(exists=True),
                                 default=None, usedefault=True)
    no_sanitize = traits.Bool(False, usedefault=True)


class MaskEPIOutputSpec(TraitedSpec):
    out_mask = File(exists=True, desc='output mask')


class MaskEPI(SimpleInterface):
    input_spec = MaskEPIInputSpec
    output_spec = MaskEPIOutputSpec

    def _run_interface(self, runtime):
        masknii = compute_epi_mask(
            self.inputs.in_files,
            lower_cutoff=self.inputs.lower_cutoff,
            upper_cutoff=self.inputs.upper_cutoff,
            connected=self.inputs.connected,
            opening=self.inputs.opening,
            exclude_zeros=self.inputs.exclude_zeros,
            ensure_finite=self.inputs.ensure_finite,
            target_affine=self.inputs.target_affine,
            target_shape=self.inputs.target_shape
        )

        if self.inputs.no_sanitize:
            in_file = self.inputs.in_files
            if isinstance(in_file, list):
                in_file = in_file[0]
            nii = nb.load(in_file)
            qform, code = nii.get_qform(coded=True)
            masknii.set_qform(qform, int(code))
            sform, code = nii.get_sform(coded=True)
            masknii.set_sform(sform, int(code))

        self._results['out_mask'] = fname_presuffix(
            self.inputs.in_files[0], suffix='_mask', newpath=runtime.cwd)
        masknii.to_filename(self._results['out_mask'])
        return runtime


class MergeInputSpec(BaseInterfaceInputSpec):
    in_files = InputMultiPath(File(exists=True), mandatory=True,
                              desc='input list of files to merge')
    dtype = traits.Enum('f4', 'f8', 'u1', 'u2', 'u4', 'i2', 'i4',
                        usedefault=True, desc='numpy dtype of output image')
    header_source = File(exists=True, desc='a Nifti file from which the header should be copied')
    compress = traits.Bool(True, usedefault=True, desc='Use gzip compression on .nii output')


class MergeOutputSpec(TraitedSpec):
    out_file = File(exists=True, desc='output merged file')


class Merge(SimpleInterface):
    input_spec = MergeInputSpec
    output_spec = MergeOutputSpec

    def _run_interface(self, runtime):
        ext = '.nii.gz' if self.inputs.compress else '.nii'
        self._results['out_file'] = fname_presuffix(
            self.inputs.in_files[0], suffix='_merged' + ext, newpath=runtime.cwd, use_ext=False)
        new_nii = concat_imgs(self.inputs.in_files, dtype=self.inputs.dtype)

        if isdefined(self.inputs.header_source):
            src_hdr = nb.load(self.inputs.header_source).header
            new_nii.header.set_xyzt_units(t=src_hdr.get_xyzt_units()[-1])
            new_nii.header.set_zooms(list(new_nii.header.get_zooms()[:3]) +
                                     [src_hdr.get_zooms()[3]])

        new_nii.to_filename(self._results['out_file'])

        return runtime
