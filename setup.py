#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: oesteban
# @Date:   2015-11-19 16:44:27
# @Last Modified by:   oesteban
# @Last Modified time: 2016-03-10 15:07:21
""" fmriprep setup script """
import os
import sys

__version__ = '0.0.1'

REQ_LINKS = []
with open('requirements.txt', 'r') as rfile:
    REQUIREMENTS = [line.strip() for line in rfile.readlines()]

for i, req in enumerate(REQUIREMENTS):
    if req.startswith('-e'):
        REQUIREMENTS[i] = req.split('=')[1]
        REQ_LINKS.append(req.split()[1])

if REQUIREMENTS is None:
    REQUIREMENTS = []

def main():
    """ Install entry-point """
    from glob import glob
    from setuptools import setup

    setup(
        name='fmriprep',
        version=__version__,
        description='',
        author_email='crn.poldracklab@gmail.com',
        url='https://github.com/poldracklab/preprocessing-workflow',
        download_url='',
        license='3-clause BSD',
        entry_points={'console_scripts': ['fmriprep=fmriprep.run_workflow:main',]},
        packages=['fmriprep', 'fmriprep.workflows', 'fmriprep.viz'],
        package_data={'fmriprep': ['data/*.nii.gz']},
        install_requires=REQUIREMENTS,
        dependency_links=REQ_LINKS,
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
