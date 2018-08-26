#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Multi-echo EPI
~~~~~~~~~~~~~~

For using multi-echo EPI data.

Change directory to provide relative paths for doctests
>>> import os
>>> filepath = os.path.dirname( os.path.realpath( __file__ ) )
>>> datadir = os.path.realpath(os.path.join(filepath, '../data/'))
>>> os.chdir(datadir)

"""
import tedana
import numpy as np

from nipype import logging
from nipype.interfaces.base import (
    traits, TraitedSpec, File, InputMultiPath, SimpleInterface,
    BaseInterfaceInputSpec)

LOGGER = logging.getLogger('nipype.interface')


class FirstEchoInputSpec(BaseInterfaceInputSpec):
    in_files = InputMultiPath(File(exists=True), mandatory=True, minlen=2,
                              desc='multi-echo BOLD EPIs')
    ref_imgs = InputMultiPath(File(exists=True), mandatory=True, minlen=2,
                              desc='generated reference image for each '
                              'multi-echo BOLD EPI')
    te_list = traits.List(traits.Float, mandatory=True, desc='echo times')


class FirstEchoOutputSpec(TraitedSpec):
    first_image = File(exists=True,
                       desc='BOLD EPI series for the first echo')
    first_ref_image = File(exists=True, desc='generated reference image for '
                                             'the first echo')


class FirstEcho(SimpleInterface):
    """
    Finds the first echo in a multi-echo series and its associated reference
    image.

    Example
    =======
    >>> from fmriprep.interfaces import multiecho
    >>> first_echo = multiecho.FirstEcho()
    >>> first_echo.inputs.in_files = ['sub-01_run-01_echo-1_bold.nii.gz', \
                                      'sub-01_run-01_echo-2_bold.nii.gz', \
                                      'sub-01_run-01_echo-3_bold.nii.gz']
    >>> first_echo.inputs.ref_imgs = ['sub-01_run-01_echo-1_bold.nii.gz', \
                                      'sub-01_run-01_echo-2_bold.nii.gz', \
                                      'sub-01_run-01_echo-3_bold.nii.gz']
    >>> first_echo.inputs.te_list = [0.013, 0.027, 0.043]
    >>> res = first_echo.run()
    >>> res.outputs.first_image
    'sub-01_run-01_echo-1_bold.nii.gz'
    >>> res.outputs.first_ref_image
    'sub-01_run-01_echo-1_bold.nii.gz'
    """
    input_spec = FirstEchoInputSpec
    output_spec = FirstEchoOutputSpec

    def _run_interface(self, runtime):
        self._results['first_image'] = self.inputs.in_files[np.argmin(self.inputs.te_list)]
        self._results['first_ref_image'] = self.inputs.ref_imgs[np.argmin(self.inputs.te_list)]

        return runtime


class T2SMapInputSpec(BaseInterfaceInputSpec):
    in_files = InputMultiPath(File(exists=True), mandatory=True, minlen=2,
                              desc='multi-echo BOLD EPIs')
    te_list = traits.List(traits.Float, mandatory=True, desc='echo times')


class T2SMapOutputSpec(TraitedSpec):
    t2sv = File(exists=True, desc='limited T2* map')
    s0v = File(exists=True, desc='limited s0 map')
    t2svG = File(exists=True, desc='adaptive T2* map')
    s0vG = File(exists=True, desc='adaptive s0 map')
    ts_OC = File(exists=True, desc='optimally combined ME-EPI time series')


class T2SMap(SimpleInterface):
    """
    Runs the tedana T2* workflow to generate an adaptive T2* map and create
    an optimally combined ME-EPI time series.

    Example
    =======
    >>> from fmriprep.interfaces import multiecho
    >>> t2smap = multiecho.T2SMap()
    >>> t2smap.inputs.in_files = ['sub-01_run-01_echo-1_bold.nii.gz', \
                                  'sub-01_run-01_echo-2_bold.nii.gz', \
                                  'sub-01_run-01_echo-3_bold.nii.gz']
    >>> t2smap.inputs.te_list = [0.013, 0.027, 0.043]
    >>> res = t2smap.run() # doctest: +SKIP
    """
    input_spec = T2SMapInputSpec
    output_spec = T2SMapOutputSpec

    def _run_interface(self, runtime):
        # tedana expects echo times in milliseconds, rather than seconds
        echo_times = [te * 1000 for te in self.inputs.te_list]

        (self._results['t2sv'], self._results['s0v'],
         self._results['t2svG'], self._results['s0vG'],
         self._results['ts_OC']) = tedana.t2smap_workflow(self.inputs.in_files, echo_times)

        return runtime
