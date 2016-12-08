FMRIPREP: A Robust Preprocessing Pipeline for fMRI Data
=======================================================

This pipeline is developed by the `Poldrack lab at Stanford University <https://poldracklab.stanford.edu/>`_
for use at the `Center for Reproducible Neuroscience (CRN) <http://reproducibility.stanford.edu/>`_,
as well as for open-source software distribution.

.. image:: https://circleci.com/gh/poldracklab/fmriprep/tree/master.svg?style=shield
  :target: https://circleci.com/gh/poldracklab/fmriprep/tree/master

.. image:: https://readthedocs.org/projects/fmriprep/badge/?version=latest
  :target: http://fmriprep.readthedocs.io/en/latest/?badge=latest
  :alt: Documentation Status

.. image:: https://img.shields.io/pypi/v/fmriprep.svg
  :target: https://pypi.python.org/pypi/fmriprep/
  :alt: Latest Version


About
-----

``fMRIprep`` is a functional magnetic resonance imaging (fMRI) data pre-processing pipeline.
It performs basic processing steps (coregistration, normalization, unwarping, 
noise component extraction, segmentation, skullstripping etc.) providing outputs that make
running a variety of group level analyses (task based or resting state fMRI, graph theory measures, surface or volume, etc.) easy.
``fMRIrep`` is build around three principles:

1. **Robustness** - the pipeline adapts the preprocessing steps depending on the input dataset and should provide results as good as possible independently of scanner make, scanning parameters or presence of additional correction scans (such as fieldmaps)
2. **Ease of use** - thanks to dependance on the BIDS standard manual parameter input is reduced to a minimum allow the pipelien to run in an automatic fashion.
3. **"Glass box"** philosophy - automation should not mean that one should not visually inspect the results or understand the methods. Thus ``fMRIprep`` provides for each subject visual reports detailing the accuracy of the most importatnt processing steps. This combined with the documentation can help researchers to understand the process and decide which subjects should be kept for the group level analysis.
