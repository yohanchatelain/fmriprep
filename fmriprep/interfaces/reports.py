#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Interfaces to generate reportlets
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


"""
from __future__ import print_function, division, absolute_import, unicode_literals

import os
from niworkflows.nipype.interfaces.base import (
    traits, TraitedSpec, BaseInterfaceInputSpec,
    File, Directory, InputMultiPath, isdefined)
from niworkflows.interfaces.base import SimpleInterface

from niworkflows.nipype.interfaces import freesurfer as fs

ANATOMICAL_TEMPLATE = """\t\t<h3 class="elem-title">Summary</h3>
\t\t<ul class="elem-desc">
\t\t\t<li>Structural images: {n_t1s:d}</li>
\t\t\t<li>FreeSurfer reconstruction: {freesurfer_status}</li>
\t\t\t<li>Output spaces: {output_spaces}</li>
\t\t</ul>
"""


class AnatomicalSummaryInputSpec(BaseInterfaceInputSpec):
    t1w = InputMultiPath(File(exists=True), desc='T1w structural images')
    subjects_dir = Directory(desc='FreeSurfer subjects directory')
    subject_id = traits.Str(desc='FreeSurfer subject ID')
    output_spaces = traits.List(desc='Target spaces')


class AnatomicalSummaryOutputSpec(TraitedSpec):
    out_report = File(exists=True, desc='HTML segment containing summary')


class AnatomicalSummary(SimpleInterface):
    input_spec = AnatomicalSummaryInputSpec
    output_spec = AnatomicalSummaryOutputSpec

    def _run_interface(self, runtime):
        if not isdefined(self.inputs.subjects_dir):
            freesurfer_status = 'Not run'
        else:
            recon = fs.ReconAll(subjects_dir=self.inputs.subjects_dir,
                                subject_id=self.inputs.subject_id,
                                T1_files=self.inputs.t1w,
                                flags='-noskullstrip')
            if recon.cmdline.startswith('echo'):
                freesurfer_status = 'Pre-existing directory'
            else:
                freesurfer_status = 'Run by FMRIPREP'

        segment = ANATOMICAL_TEMPLATE.format(n_t1s=len(self.inputs.t1w),
                                             freesurfer_status=freesurfer_status,
                                             output_spaces=', '.join(self.inputs.output_spaces))

        fname = os.path.abspath('report.html')
        with open(fname, 'w') as fobj:
            fobj.write(segment)

        self._results['out_report'] = fname

        return runtime
