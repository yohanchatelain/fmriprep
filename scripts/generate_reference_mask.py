#!/usr/bin/env python
import sys
import os
from niworkflows.nipype.pipeline import engine as pe
from niworkflows.nipype.interfaces import utility as niu
from niworkflows.nipype.utils.filemanip import fname_presuffix, copyfile
from fmriprep.workflows.bold.utils import init_bold_reference_wf


def sink_ref_file(in_file, orig_file, out_dir):
    out_file = fname_presuffix(orig_file, suffix='_ref', newpath=out_dir)
    copyfile(in_file, out_file)
    return out_file


def init_main_wf(bold_file, out_dir, base_dir=None, name='main_wf'):
    wf = init_bold_reference_wf(enhance_t2=True,
                                base_dir=base_dir,
                                name=name)
    wf.inputs.inputnode.bold_file = bold_file

    sink = pe.Node(Function(function=sink_ref_file, out_dir=out_dir,
                            orig_file=bold_file),
                   name='sink')
    wf.connect([
        ('outputnode', 'sink', [('bold_mask', 'in_file')]),
        ])


def main():
    main_wf = init_main_wf(sys.argv[1], sys.argv[2])
    main_wf.run()
