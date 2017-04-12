#!/usr/bin/env python
# -*- coding: utf-8 -*-
""" fmriprep wrapper setup script """

from setuptools import setup, find_packages
from codecs import open
from os import path as op
import runpy

long_description = """\
This package is a basic wrapper for fMRIprep that generates the appropriate
Docker commands, providing an intuitive interface to running the fMRIprep
workflow in a Docker environment."""


def main():
    """ Install entry-point """
    this_path = op.abspath(op.dirname(__file__))
    info_path = op.join(op.dirname(this_path), 'fmriprep', 'info.py')

    info = runpy.run_path(info_path)

    setup(
        name='{}-docker'.format(info['__packagename__']),
        version=info['__version__'],
        description=info['__description__'],
        long_description=long_description,
        author=info['__author__'],
        author_email=info['__email__'],
        maintainer=info['__maintainer__'],
        maintainer_email=info['__email__'],
        url=info['__url__'],
        license=info['__license__'],
        classifiers=info['CLASSIFIERS'],
        download_url=info['WRAPPER_URL'],
        # Dependencies handling
        setup_requires=[],
        install_requires=[],
        tests_require=[],
        extras_require={},
        dependency_links=[],
        package_data={},
        py_modules=["fmriprep-docker"],
        entry_points={'console_scripts': ['fmriprep-docker=fmriprep-docker:main',]},
        packages=find_packages(),
        zip_safe=False
    )

if __name__ == '__main__':
    main()
