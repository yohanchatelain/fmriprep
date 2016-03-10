#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: oesteban
# @Date:   2015-11-19 16:44:27
# @Last Modified by:   oesteban
# @Last Modified time: 2016-03-10 12:45:51
""" fmriprep setup script """
import os
import sys

__version__ = '0.0.1'


def main():
    """ Install entry-point """
    from glob import glob
    from setuptools import setup

    setup(
        name='mriqc',
        version=__version__,
        description='',
        author_email='crn.poldracklab@gmail.com',
        url='https://github.com/poldracklab/mriqc',
        download_url='',
        license='3-clause BSD',
        entry_points={'console_scripts': ['mriqc=fmriprep.run_workflow:main',]},
        packages=['fmriprep', 'fmriprep.workflows', 'fmriprep.viz'],
        # package_data={'fmriprep': ['data/*.txt']},
        install_requires=['numpy', 'nipype', 'nibabel'],
        zip_safe=False,
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Intended Audience :: MRI processing',
            'Topic :: Scientific/Engineering :: Biomedical Imaging',
            'License :: OSI Approved :: 3-clause BSD License',
            'Programming Language :: Python :: 2.7',
        ],
    )

if __name__ == '__main__':
    local_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    os.chdir(local_path)
    sys.path.insert(0, local_path)

    main()
