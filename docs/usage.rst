.. include:: links.rst

Usage
-----

.. warning::
   As of FMRIPREP 1.0.12, the software includes a tracking system
   to report usage statistics and errors. Users can opt-out using
   the ``--notrack`` command line argument.
   

Execution and the BIDS format
=============================

The ``fmriprep`` workflow takes as principal input the path of the dataset
that is to be processed.
The input dataset is required to be in valid :abbr:`BIDS (Brain Imaging Data
Structure)` format, and it must include at least one T1w structural image and
(unless disabled with a flag) a BOLD series.
We highly recommend that you validate your dataset with the free, online
`BIDS Validator <http://bids-standard.github.io/bids-validator/>`_.

The exact command to run ``fmriprep`` depends on the Installation_ method.
The common parts of the command follow the `BIDS-Apps
<https://github.com/BIDS-Apps>`_ definition.
Example: ::

    fmriprep data/bids_root/ out/ participant -w work/


Command-Line Arguments
======================

.. argparse::
   :ref: fmriprep.cli.run.get_parser
   :prog: fmriprep
   :nodefault:
   :nodefaultconst:

Defining standard and nonstandard spaces where data will be resampled
=====================================================================

The command line interface of fMRIPrep allows resampling the preprocessed data
onto other output spaces.
That is achieved using the ``--output-spaces`` argument, where standard and
nonstandard spaces can be inserted.

Standard spaces
---------------

When using fMRIPrep in a workflow that will investigate effects that span across
analytical groupings, neuroimagers typically resample their data on to a standard,
stereotactic coordinate system.
The most extended standard space for fMRI analyses is generally referred to MNI.
For instance, to instruct fMRIPrep to use the MNI template brain distributed with
FSL as coordinate reference the option will read as follows: ``--output-spaces MNI152NLin6Asym``.
By default, fMRIPrep uses ``MNI152NLin2009cAsym`` as spatial-standardization reference.
Valid template identifiers (``MNI152NLin6Asym``, ``MNI152NLin2009cAsym``, etc.) come from
the `TemplateFlow project <https://github.com/templateflow/templateflow>`__.

Therefore, fMRIPrep will run nonlinear registration processes against the template
T1w image corresponding to all the standard spaces supplied with the argument
``--output-spaces``.
By default, fMRIPrep will resample the preprocessed data on those spaces (labeling the
corresponding outputs with the `space-<template-identifier>` BIDS entity) but keeping
the original resolution of the BOLD data to produce smaller files, more consistent with
the original data gridding.
However, many users will be interested in utilizing a coarse gridding (typically 2mm isotropic)
of the target template.
Such a behavior can be achieved applying modifiers to the template identifier, separated by
a ``:`` character. 
For instance, ``--output-spaces MNI152NLin6Asym:res-2 MNI152NLin2009cAsym`` will generate
preprocessed BOLD 4D files on two standard spaces (``MNI152NLin6Asym``, 
and ``MNI152NLin2009cAsym``) with the template's 2mm isotropic resolution for
the data on ``MNI152NLin6Asym`` space and the original BOLD resolution
(say, e.g., 2x2x2.5 [mm]) for the case of ``MNI152NLin2009cAsym``.

Other possible modifiers are, for instance, the ``cohort`` selector.
Although currently there is no template in TemplateFlow with several cohorts,
very soon we will integrate pediatric templates, for which ``cohort`` will
function to select the appropriate age range.
Therefore, in upcoming versions of fMRIPrep, it will be possible to run it with
``--output-spaces MNIPediatricAsym:res-2:cohort-2`` where ``cohort-2`` would select
the template instance for the, say, 24-48 months old range.

When specifying surface spaces (e.g. ``fsaverage``), the legacy identifiers from
FreeSurfer will be supported (e.g. ``fsaverage5``) although the use of the density
modifier would be preferred (i.e. ``fsaverage:den-10k`` for ``fsaverage5``).

Custom standard spaces
----------------------

Although the functionality is not available yet, the interface of the
``--output-spaces`` permits providing paths to custom templates that
follow TemplateFlow's naming conventions
(e.g. ``/path/to/custom/templates/tpl-MyCustom:res-2``).
Following the example, at least the following files
must be found under under ``/path/to/custom/templates/tpl-MyCustom``: ::

  tpl-MyCustom/
      template_description.json
      tpl-MyCustom_res-1_T1w.nii.gz
      tpl-MyCustom_res-1_desc-brain_mask.nii.gz
      tpl-MyCustom_res-2_T1w.nii.gz
      tpl-MyCustom_res-2_desc-brain_mask.nii.gz

Although a more comprehensive coverage of standard files would be advised.

Nonstandard spaces
------------------

Additionally, ``--output-spaces`` accepts identifiers of spatial references
that do not generate *standardized* coordinate spaces:

  * ``T1w`` or ``anat``: data are resampled into the individual's anatomical
    reference generated with the T1w and T2w images available within the 
    BIDS structure.
  * ``fsnative``: similarly to the ``anat`` space for volumetric references,
    including the ``fsnative`` space will instruct fMRIPrep to sample the
    original BOLD data onto FreeSurfer's reconstructed surfaces for this
    individual.
  * **Additional nonstandard spaces** that will be supported in the future are
    ``run``, ``func``, and ``sbref``.

Modifiers are not allowed when providing nonstandard spaces.

Preprocessing blocks depending on standard templates
----------------------------------------------------

Some modules of the pipeline (e.g. the ICA-AROMA denoising, the generation of
HCP compatible *grayordinates* files, or the *fieldmap-less* distortion correction)
perform on specific template spaces.
When selecting those modules to be included (using any of the following flags:
``--use-aroma``, ``--cifti-outputs``, ``--use-syn-sdc``) will modify the list of
output spaces to include the space identifiers they require, should the
identifier not be found within the ``--output-spaces`` list already.
In other words, running fMRIPrep with ``--output-spaces MNI152NLin6Asym:res-2
--use-syn-sdc`` will expand the list of output spaces to be
``MNI152NLin6Asym:res-2 MNI152NLin2009cAsym``.


The docker wrapper CLI
======================

.. argparse::
   :ref: fmriprep_docker.get_parser
   :prog: fmriprep-docker
   :nodefault:
   :nodefaultconst:


Debugging
=========

Logs and crashfiles are outputted into the
``<output dir>/fmriprep/sub-<participant_label>/log`` directory.
Information on how to customize and understand these files can be found on the
`nipype debugging <http://nipype.readthedocs.io/en/latest/users/debug.html>`_
page.

Support and communication
=========================

The documentation of this project is found here: http://fmriprep.readthedocs.org/en/latest/.

All bugs, concerns and enhancement requests for this software can be submitted here:
https://github.com/poldracklab/fmriprep/issues.

If you have a problem or would like to ask a question about how to use ``fmriprep``,
please submit a question to `NeuroStars.org <http://neurostars.org/tags/fmriprep>`_ with an ``fmriprep`` tag.
NeuroStars.org is a platform similar to StackOverflow but dedicated to neuroinformatics.

All previous ``fmriprep`` questions are available here:
http://neurostars.org/tags/fmriprep/

To participate in the ``fmriprep`` development-related discussions please use the
following mailing list: http://mail.python.org/mailman/listinfo/neuroimaging
Please add *[fmriprep]* to the subject line when posting on the mailing list.


Not running on a local machine? - Data transfer
===============================================

If you intend to run ``fmriprep`` on a remote system, you will need to
make your data available within that system first.

For instance, here at the Poldrack Lab we use Stanford's
:abbr:`HPC (high-performance computing)` system, called Sherlock.
Sherlock enables `the following data transfer options 
<https://www.sherlock.stanford.edu/docs/user-guide/storage/data-transfer/>`_.

Alternatively, more comprehensive solutions such as `Datalad
<http://www.datalad.org/>`_ will handle data transfers with the appropriate
settings and commands.
Datalad also performs version control over your data.
