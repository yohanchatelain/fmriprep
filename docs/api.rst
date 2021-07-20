.. include:: links.rst

================
Developers - API
================
The *NiPreps* community and contributing guidelines
---------------------------------------------------
*fMRIPrep* is a *NiPreps* application, and abides by the
`NiPreps Community guidelines <https://www.nipreps.org/community/>`__.
Please, make sure you have read and understood all the documentation
provided in the `NiPreps portal <https://www.nipreps.org>`__ before
you get started.

Setting up your development environment
---------------------------------------
Making changes to *fMRIPrep* and creating derived works is easy.
To setup your environment, we recommend 
`the following tips and the use of containers <https://www.nipreps.org/devs/devenv/>`__.

Internal configuration system
-----------------------------

.. automodule:: fmriprep.config
   :members: from_dict, load, get, dumps, to_filename, init_spaces

Workflows
---------

.. automodule:: fmriprep.workflows.base
.. automodule:: fmriprep.workflows.bold
