#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
T2* map generation
~~~~~~~~~~~~~~~~~~~~~~

Using multi-echo EPI data, generates a T2*-map
for use in T2*-driven EPI->T1 coregistration
"""
import os
import numpy as np
import nibabel as nb

from niworkflows.nipype import logging
from niworkflows.nipype.utils.filemanip import split_filename
from niworkflows.nipype.interfaces.base import (
    traits, TraitedSpec, File, InputMultiPath, SimpleInterface,
    BaseInterfaceInputSpec)

LOGGER = logging.getLogger('interface')


class T2SMapInputSpec(BaseInterfaceInputSpec):
    in_files = InputMultiPath(File(exists=True), mandatory=True,
                              desc='multi-echo BOLD EPIs')
    te_list = traits.List(traits.Float, mandatory=True, desc='echo times')
    compress = traits.Bool(True, usedefault=True, desc='use gzip compression on .nii output')


class T2SMapOutputSpec(TraitedSpec):
    output_image = File(exists=True, desc='T2* map')


class T2SMap(SimpleInterface):
    input_spec = T2SMapInputSpec
    output_spec = T2SMapOutputSpec

    def _run_interface(self, runtime):
        ext = '.nii.gz' if self.inputs.compress else '.nii'
        last_emask, two_emask = echo_sampling_mask(self.inputs.in_files)
        t2s_map = define_t2s_map(self.inputs.in_files, self.inputs.te_list,
                                 last_emask, two_emask)
        _, fname, _ = split_filename(self.inputs.in_files[0])
        fname_preecho = fname.split('_echo-')[0]
        self._results['t2s_map'] = os.path.join(runtime.cwd, fname_preecho + '_t2smap' + ext)
        t2s_map.to_filename(self._results['out_file'])
        return runtime


def echo_sampling_mask(echo_list):
    """
    Make a map of longest echo that a voxel can be sampled with,
    with minimum value of map as X value of voxel that has median
    value in the 1st echo. N.B. larger factor leads to bias to lower TEs

    **Inputs**

        echo_list
            List of file names for all echos

    **Outputs**

        last_echo_mask
            numpy array whose values correspond to which
            echo a voxel can last be sampled with
        two_echo_mask
            boolean array of voxels that can be sampled
            with at least two echos

    """
    # First, load each echo and average over time
    echos = [np.mean(nb.load(e).get_data(), axis=-1) for e in echo_list]

    # In the first echo, find the 33rd percentile and the voxel(s)
    # whose average activity is equal to that value
    perc33 = np.percentile(echos[0][echos[0].nonzero()],
                           33, interpolation="higher")
    med_vox = (echos[0] == perc33)

    # For each (averaged) echo, extract the max signal in the
    # identified voxels and divide it by 3-- save as a threshold
    thrs = np.hstack([np.max(echo[med_vox]) / 3 for echo in echos])

    # Let's stack the arrays to make this next bit easier
    emeans = np.stack(echos, axis=-1)

    # Now, we want to find all voxels (in each echo) that show
    # absolute signal greater than our echo-specific threshold
    mthr = np.ones_like(emeans)
    mthr *= thrs[np.newaxis, np.newaxis, np.newaxis, :]
    voxels = np.abs(emeans) > mthr

    # We save those voxel indices out to an array
    last_emask = np.array(voxels, dtype=np.int).sum(-1)
    # Save a mask of voxels sampled by at least two echos
    two_emask = (last_emask != 0)

    return last_emask, two_emask


def define_t2s_map(echo_list, tes, last_emask, two_emask):
    """
    Computes the quantiative T2* mapping according to
    :math:`ΔS/S = ΔS0/S0 − ΔR2 * TE`.

    **Inputs**

        echo_list
            list of file names for all echos
        tes
            echo times for the multi-echo EPI run
        last_emask
            numpy array where voxel values correspond to which
            echo a voxel can last be sampled with
        two_emask
            boolean array of voxels that can be sampled
            with at least two echos

    **Outputs**

        t2s_map
            the T2* map for the EPI run
    """
    # get some basic shape information
    echo_stack = np.stack([nb.load(echo).get_data() for echo in echo_list],
                          axis=-2)
    nx, ny, nz, necho, nt = echo_stack.shape

    # create empty arrays to fill later
    t2ss = np.zeros([nx, ny, nz, necho - 1])
    s0vs = t2ss.copy()

    # consider only those voxels sampled by at least two echos
    two_edata = echo_stack[two_emask.nonzero()]
    two_echo_nvox = two_edata.shape[0]

    # for the second echo on, do log linear fit
    for echo in range(2, necho + 1):

        # ΔS/S = ΔS0/S0 − ΔR2 * TE, so take neg TEs
        neg_tes = [-1 * te for te in tes[:echo]]

        # Create coefficient matrix
        a = np.array([np.ones(echo), neg_tes])
        A = np.tile(a, (1, nt))
        A = np.sort(A)[:, ::-1].transpose()

        # Create log-scale dependent-var matrix
        B = np.reshape(np.abs(two_edata[:, :echo, :]) + 1,
                       (two_echo_nvox, echo * nt)).transpose()
        B = np.log(B)

        # find the least squares solution for the echo
        X, res, rank, sing = np.linalg.lstsq(A, B)

        # scale the echo-coefficients (ΔR2), intercept (s0)
        r2 = 1 / X[1, :].transpose()
        s0 = np.exp(X[0, :]).transpose()

        # fix any non-numerical values
        r2[np.isinf(r2)] = 500.
        s0[np.isnan(s0)] = 0.

        # reshape into arrays for mapping
        r2[:, :, :, echo - 2] = _unmask(r2, two_emask)
        s0vs[:, :, :, echo - 2] = _unmask(s0, two_emask)

    # limited T2* and S0 maps
    fl = np.zeros([nx, ny, nz, necho - 1])
    for echo in range(necho - 1):
        fl_ = fl[:, :, :, echo]
        fl_[last_emask == echo + 2] = True
        fl[:, :, :, echo] = fl_

    fl = np.array(fl, dtype=bool)
    t2s_map = np.squeeze(_unmask(r2[fl], last_emask > 1))
    t2s_map[np.logical_or(np.isnan(t2s_map), t2s_map < 0)] = 0

    return t2s_map


def _unmask(data, mask):
    """
    Unmasks `data` using non-zero entries of `mask`

    **Inputs**

    data
        Masked array of shape (nx*ny*nz[, Ne[, nt]])
    mask
        Boolean array of shape (nx, ny, nz)

    **Outputs**

    ndarray
        Array of shape (nx, ny, nz[, Ne[, nt]])

    """

    M = (mask != 0).ravel()
    Nm = M.sum()

    nx, ny, nz = mask.shape

    if len(data.shape) > 1:
        nt = data.shape[1]
    else:
        nt = 1

    out = np.zeros((nx * ny * nz, nt), dtype=data.dtype)
    out[M, :] = np.reshape(data, (Nm, nt))

    return np.squeeze(np.reshape(out, (nx, ny, nz, nt)))
