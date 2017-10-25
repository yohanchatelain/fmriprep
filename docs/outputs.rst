

.. _outputs:

-------------------
Outputs of FMRIPREP
-------------------

FMRIPREP generates three broad classes of outcomes:

  1. **Pre-processed imaging data** which are derivatives of the original
     anatomical and functional images after various preparation procedures
     have been applied. For example, 
     :abbr:`INU (intensity non-uniformity)`-corrected versions of the T1-weighted
     image (per subject), the brain mask, or :abbr:`BOLD (blood-oxygen level dependent)`
     images after head-motion correction, slice-timing correction and aligned into
     the same-subject's T1w space or into MNI space.

  2. **Additional data for subsequent analysis**, for instance the transformations
     between different spaces or the estimated confounds.

  3. **Visual :abbr:`QA (quality assessment)` reports**: 
     one :abbr:`HTML (hypertext markup language)` per subject,
     that allows the user a thorough visual assessment of the quality
     of processing.


In general, FMRIPREP follows the current working draft of the
:abbr:`BIDS (brain imaging data structure)`-derivatives extension.


.. Pre-processed data
.. ------------------


Confounds
---------

For each :abbr:`BOLD (blood-oxygen level dependent)` run processed with FMRIPREP, a
``<output_folder>/fmriprep/sub-<sub_id>/func/sub-<sub_id>_task-<task_id>_run-<run_id>_confounds.tsv``
file will be generated.
These are :abbr:`TSV (tab-separated values)` tables, which look like the example below: ::

  WhiteMatter GlobalSignal    stdDVARS    non-stdDVARS    vx-wisestdDVARS FramewiseDisplacement   tCompCor00  tCompCor01  tCompCor02  tCompCor03  tCompCor04  tCompCor05  aCompCor00  aCompCor01  aCompCor02  aCompCor03  aCompCor04  aCompCor05  NonSteadyStateOutlier00 X   Y   Z   RotX    RotY    RotZ    AROMAAggrComp01 AROMAAggrComp03 AROMAAggrComp04 AROMAAggrComp05
  0.63    2.72    n/a n/a n/a n/a 0.00    0.00    0.00    0.00    0.00    0.00    0.00    0.00    0.00    0.00    0.00    0.00    1.00    0.00    0.00    0.00    0.00    0.00    0.00    2.62    -1.12   -0.03   3.12
  3.14    0.51    1.18    16.05   1.21    0.07    -0.21   -0.36   -0.23   0.29    -0.37   0.04    -0.33   -0.54   -0.36   0.22    -0.07   0.16    0.00    0.00    0.02    0.05    0.00    0.00    0.00    1.66    -1.74   -0.38   -0.99
  -1.23   -0.85   1.09    14.86   1.11    0.03    0.02    0.04    -0.22   -0.08   -0.18   0.66    0.11    -0.45   -0.16   -0.28   -0.05   0.26    0.00    0.00    0.00    0.05    0.00    0.00    0.00    0.35    -1.22   0.10    -0.23
  -1.61   -1.53   1.01    13.83   1.05    0.03    0.27    0.21    -0.07   0.21    0.30    -0.02   0.24    -0.15   0.24    0.17    0.51    -0.02   0.00    0.01    -0.01   0.04    0.00    0.00    0.00    -0.42   -0.55   0.49    -0.38
  -3.43   -1.48   0.98    13.32   1.02    0.03    0.06    0.49    0.24    -0.18   0.06    0.12    0.25    0.11    0.09    -0.10   0.08    0.47    0.00    0.02    -0.01   0.03    0.00    0.00    0.00    -1.12   -0.40   0.21    1.23
  0.71    -0.66   0.97    13.26   1.02    0.04    -0.29   0.43    0.14    0.06    -0.20   -0.32   0.40    0.22    -0.07   0.45    -0.02   -0.04   0.00    0.02    -0.02   0.03    0.00    0.00    0.00    -1.00   -0.91   -0.99   0.30
  -2.81   0.61    0.95    12.98   1.01    0.08    -0.48   0.24    -0.11   -0.15   -0.16   -0.22   0.38    0.20    -0.35   0.16    -0.31   -0.01   0.00    0.00    0.00    0.05    0.00    0.00    0.00    -0.66   -0.49   -1.89   0.43
  2.85    0.35    0.95    12.99   1.01    0.04    -0.22   0.00    -0.50   0.05    0.15    0.14    0.30    -0.20   -0.22   -0.22   0.04    -0.34   0.00    0.00    -0.01   0.03    0.00    0.00    0.00    0.01    0.22    -1.76   -0.39
  -2.57   -0.54   1.04    14.22   1.07    0.05    0.45    0.01    -0.43   -0.51   -0.01   -0.20   0.13    -0.02   0.26    -0.62   0.00    -0.30   0.00    0.00    0.00    0.06    0.00    0.00    0.00    0.60    1.59    0.05    -0.46
  3.41    -0.72   1.03    14.04   1.05    0.07    0.37    0.06    0.08    0.55    -0.21   -0.14   -0.10   -0.18   0.51    0.17    -0.24   0.05    0.00    0.00    0.02    0.07    0.00    0.00    0.00    0.52    0.71    1.63    -0.95
  3.75    -0.54   1.01    13.83   1.04    0.06    0.16    -0.16   0.38    -0.19   -0.01   0.16    -0.11   0.18    0.37    0.00    -0.43   0.20    0.00    0.00    0.00    0.06    0.00    0.00    0.00    -0.53   -0.07   1.85    -0.01
  0.41    1.19    1.05    14.28   1.08    0.06    -0.27   -0.38   0.32    -0.11   0.10    0.07    -0.31   0.31    -0.25   -0.24   -0.01   0.27    0.00    0.00    0.01    0.09    0.00    0.00    0.00    -0.75   -0.03   0.14    -0.26
  -4.14   0.72    0.97    13.20   1.01    0.03    -0.13   -0.28   0.03    -0.16   0.48    -0.28   -0.26   0.40    -0.24   -0.10   0.18    -0.20   0.00    0.00    0.00    0.08    0.00    0.00    0.00    -0.44   1.03    -0.50   -0.15
  2.21    -0.02   0.96    13.09   1.00    0.01    0.18    -0.26   -0.04   0.14    -0.05   -0.37   -0.26   -0.10   0.07    0.25    -0.10   -0.54   0.00    0.00    0.00    0.08    0.00    0.00    0.00    0.28    1.54    0.12    -0.77
  0.08    -0.06   0.95    12.89   0.99    0.01    0.15    -0.12   0.31    -0.22   -0.37   0.08    -0.22   0.12    -0.02   0.01    -0.15   -0.10   0.00    0.00    0.00    0.08    0.00    0.00    0.00    -0.46   1.00    0.70    0.08
  -1.41   0.29    0.96    13.06   0.99    0.01    -0.04   0.07    0.10    0.31    0.47    0.27    -0.22   0.09    0.11    0.12    0.56    0.14    0.00    0.00    0.00    0.07    0.00    0.00    0.00    -0.67   0.44    0.25    -0.57


Each row of the file corresponds to one time point found in the 
corresponding :abbr:`BOLD (blood-oxygen level dependent)` time-series
(stored in ``<output_folder>/fmriprep/sub-<sub_id>/func/sub-<sub_id>_task-<task_id>_run-<run_id>_bold_preproc.nii.gz``).

Columns represent the different confounds: ``WhiteMatter`` is the average signal inside the white-matter mask across time;
``GlobalSignal`` corresponds to the global-signal within the whole-brain masK; three columns relate to the
derivative of RMS variance over voxels (or :abbr:`DVARS (D referring to difference, )`) that can be
standardized (``stdDVARS``), non-standardized (``non-stdDVARS``), and voxel-wise standardized (``vx-wisestdDVARS``);
the ``FrameDisplacement`` is a quantification of the estimated bulk-head motion; ``X``, ``Y``, ``Z``, ``RotX``,
``RotY``, ``RotZ`` are the actual 6 rigid-body transform parameters estimated by FMRIPREP; 
the ``NonSteadyStateOutlier00`` column is ``1`` when a non-steady state was found (typically at the beginning of
the scan) and ``0`` elsewhere; and finally six noise components ``aCompCorXX`` calculated using 
:abbr:`CompCor (Component Based Noise Correction Method)` 
and five noise components ``AROMAaggrCompXX`` if 
:abbr:`ICA (independent components analysis)`-:abbr:`AROMA (Automatic Removal Of Motion Artifacts)` was enabled.

All these confounds can be used to perform *scrubbing* and *censoring* of outliers, 
in the subsequent first-level analysis when building the design matrix,
and in group level analysis.

.. Visual reports
.. --------------