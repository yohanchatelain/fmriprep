# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
A tool to generate a tasks_list.sh file for running fmriprep
on subjects downloaded with datalad with sample_openfmri.py


"""

import os
import glob

CMDLINE = """\
{fmriprep_cmd} {bids_dir}/{dataset_dir} {dataset_dir}/out/ participant \
-w {dataset_dir}/work --participant_label {participant_label} \
--mem-mb 96000 --nthreads 68 --omp-nthreads 12\
"""


def get_parser():
    """Build parser object"""
    from argparse import ArgumentParser
    from argparse import RawTextHelpFormatter

    parser = ArgumentParser(
        description='OpenfMRI participants sampler, for FMRIPREP\'s testing purposes',
        formatter_class=RawTextHelpFormatter)

    parser.add_argument('openfmri_dir', action='store',
                        help='the root folder of a the openfmri dataset')

    parser.add_argument('sample_file', action='store',
                        help='a YAML file containing the subsample schedule')

    # optional arguments
    parser.add_argument('--anat-only', action='store_true', default=False,
                        help='run only anatomical workflow')
    parser.add_argument('-o', '--output-file', default='tasks_list.sh',
                        action='store', help='write output file')

    parser.add_argument('--cmd-call', action='store', help='command to be run')

    return parser


def main():
    """Entry point"""
    import yaml
    opts = get_parser().parse_args()

    with open(opts.sample_file) as sfh:
        sampledict = yaml.load(sfh)

    cmdline = CMDLINE
    if opts.anat_only:
        cmdline += ' --anat-only'

    fmriprep_cmd = 'fmriprep'
    if opts.cmd_call is None:
        singularity_dir = os.getenv('SINGULARITY_BIN')
        singularity_img = sorted(
            glob.glob(os.path.join(singularity_dir, 'poldracklab_fmriprep_1*')))
        if singularity_img:
            fmriprep_cmd = 'singularity run %s' % singularity_img[-1]


    task_cmds = []
    for dset, sublist in sampledict.items():
        os.mkdir(dset)

        for sub in sublist:
            cmd = cmdline.format(
                fmriprep_cmd=fmriprep_cmd,
                bids_dir=opts.openfmri_dir,
                dataset_dir=dset,
                participant_label=sub,
            )
            task_cmds.append(cmd)

    with open(opts.output_file, 'w') as tlfile:
        tlfile.write('\n'.join(task_cmds))

if __name__ == '__main__':
    main()
