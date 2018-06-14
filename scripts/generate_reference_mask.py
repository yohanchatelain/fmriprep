#!/usr/bin/env python
import sys
import os
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu
from nipype.utils.filemanip import fname_presuffix, copyfile
from fmriprep.workflows.bold.util import init_bold_reference_wf


def sink_ref_file(in_file, orig_file, out_dir):
    out_file = fname_presuffix(orig_file, suffix='_ref', newpath=out_dir)
    copyfile(in_file, out_file)
    return out_file


def init_main_wf(bold_file, out_dir, base_dir=None, name='main_wf'):
    wf = init_bold_reference_wf(enhance_t2=True,
                                omp_nthreads=4,
                                name=name)
    wf.base_dir = base_dir
    wf.inputs.inputnode.bold_file = bold_file

    sink = pe.Node(niu.Function(function=sink_ref_file, out_dir=out_dir,
                            orig_file=bold_file),
                   name='sink')
    wf.connect([
        (wf.get_node('outputnode'), sink, [('bold_mask', 'in_file')]),
        ])
    return wf


def main():
    main_wf = init_main_wf(sys.argv[1], sys.argv[2])
    main_wf.run(plugin='MultiProc')


if __name__ == '__main__':
    main()
