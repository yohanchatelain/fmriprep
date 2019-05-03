.. include:: links.rst

========================
FAQ, Tips, and Tricks
========================

Should I run quality control of my images before running fMRIPrep?
--------------------------------------------------------------------

Yes. You should as well before any other processing/analysis.

Oftentimes (more often than we would like), images have fatal artifacts and problems. 
Those would not pass any QC check.
Some other times, QC checks will flag some images that we should carefully track throughout processing.

When using publicly available datasets, an additional concern is that images may have gone through some kind of preprocessing (see next question).


What if I find some images have undergone some pre-processing already (e.g., my T1w image is already skull-stripped)?
---------------------------------------------------------------------------------------------------------------------------

These images imply an unknown level of preprocessing (e.g. was it already bias-field corrected?), which makes it difficult to decide on best-practices for further processing.
Hence, supporting such images was considered very low priority for fMRIPrep.
For example, see `#707 <https://github.com/poldracklab/smriprep/issues/12>`_ and an illustration of downstream consequences in `#939 <https://github.com/poldracklab/fmriprep/issues/939>`_).

So for OpenFMRI, we've been excluding these subjects, and for user-supplied data, we would recommend reverting to the original, defaced, T1w images to ensure more uniform preprocessing.


My fMRIPrep run is hanging...
---------------------------------

There is a Python bug that affects fMRIPrep when processes are killed for running out of memory. 
While we are working on finding a solution that does not run up against this bug, this may take some time. 
This can be most easily resolved by allocating more memory to the process, if possible. 
Additionally, consider using the ``--low-mem`` flag, which will make some memory optimizations at the cost of disk space in the working directory.
