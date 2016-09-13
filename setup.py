#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: oesteban
# @Date:   2015-11-19 16:44:27
# @Last Modified by:   oesteban
# @Last Modified time: 2016-09-13 11:23:23
""" fmriprep setup script """
from io import open


def main():
    """ Install entry-point """
    from os import path as op
    from glob import glob
    from inspect import getfile, currentframe
    from setuptools import setup, find_packages

    this_path = op.dirname(op.abspath(getfile(currentframe())))

    # Python 3: use a locals dictionary
    # http://stackoverflow.com/a/1463370/6820620
    ldict = locals()
    # Get version and release info, which is all stored in fmriprep/info.py
    module_file = op.join(this_path, 'fmriprep', 'info.py')
    with open(module_file) as infofile:
        pythoncode = [line for line in infofile.readlines() if not line.strip().startswith('#')]
        exec('\n'.join(pythoncode), globals(), ldict)

    setup(
        name=ldict['__packagename__'],
        version=ldict['__version__'],
        description=ldict['__description__'],
        long_description=ldict['__longdesc__'],
        author=ldict['__author__'],
        author_email=ldict['__email__'],
        email=ldict['__email__'],
        maintainer=ldict['__maintainer__'],
        maintainer_email=ldict['__email__'],
        url=ldict['__url__'],
        license=ldict['__license__'],
        setup_requires=[],
        install_requires=ldict['REQUIRES'],
        download_url='https://pypi.python.org/packages/source/f/fmriprep/'
                     'fmriprep-%s.tar.gz' % ldict['__version__'],
        dependency_links=ldict['LINKS_REQUIRES'],
        package_data={'fmriprep': ['data/*.json']},
        entry_points={'console_scripts': ['fmriprep=fmriprep.run_workflow:main',]},
        packages=find_packages(),
        zip_safe=False,
        classifiers=ldict['CLASSIFIERS']
    )

if __name__ == '__main__':
    main()
