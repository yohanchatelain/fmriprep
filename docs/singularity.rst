.. include:: links.rst


.. _run_singularity:

Running *fMRIPrep* via Singularity containers
=============================================
Preparing a Singularity image
-----------------------------
**Singularity version >= 2.5**.
If the version of Singularity installed on your :abbr:`HPC (High-Performance Computing)`
system is modern enough you can create Singularity image directly on the system.
This is as simple as: ::

    $ singularity build /my_images/fmriprep-<version>.simg docker://poldracklab/fmriprep:<version>

where ``<version>`` should be replaced with the desired version of *fMRIPrep* that you
want to download.

**Singularity version < 2.5**.
In this case, start with a machine (e.g., your personal computer) with Docker installed.
Use `docker2singularity <https://github.com/singularityware/docker2singularity>`_ to
create a singularity image.
You will need an active internet connection and some time. ::

    $ docker run --privileged -t --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v D:\host\path\where\to\output\singularity\image:/output \
        singularityware/docker2singularity \
        poldracklab/fmriprep:<version>

Where ``<version>`` should be replaced with the desired version of *fMRIPrep* that you want
to download.

Beware of the back slashes, expected for Windows systems.
For \*nix users the command translates as follows: ::

    $ docker run --privileged -t --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v /absolute/path/to/output/folder:/output \
        singularityware/docker2singularity \
        poldracklab/fmriprep:<version>


Transfer the resulting Singularity image to the HPC, for example, using ``scp``. ::

    $ scp poldracklab_fmriprep*.img user@hcpserver.edu:/my_images

Running a Singularity Image
---------------------------
If the data to be preprocessed is also on the HPC, you are ready to run *fMRIPrep*. ::

    $ singularity run --cleanenv fmriprep.simg \
        path/to/data/dir path/to/output/dir \
        participant \
        --participant-label label

Handling environment variables
------------------------------
Singularity by default `exposes all environment variables from the host inside
the container <https://github.com/singularityware/singularity/issues/445>`__.
Because of this, your host libraries (e.g., nipype_ or a Python 2.7 environment)
could be accidentally used instead of the ones inside the container.
To avoid such a situation, we recommend using the ``--cleanenv`` argument in
all scenarios. For example: ::

    $ singularity run --cleanenv fmriprep.simg \
      /work/04168/asdf/lonestar/ $WORK/lonestar/output \
      participant \
      --participant-label 387 --nthreads 16 -w $WORK/lonestar/work \
      --omp-nthreads 16


Alternatively, conflicts might be preempted and some problems mitigated by
unsetting potentially problematic settings, such as the ``PYTHONPATH`` variable,
before running: ::

    $ unset PYTHONPATH; singularity run fmriprep.simg \
      /work/04168/asdf/lonestar/ $WORK/lonestar/output \
      participant \
      --participant-label 387 --nthreads 16 -w $WORK/lonestar/work \
      --omp-nthreads 16

It is possible to define environment variables scoped within the container by
using the ``SINGULARITYENV_*`` magic, in combination with ``--cleanenv``.
For example, we can set the FreeSurfer license variable (see :ref:`fs_license`)
as follows: ::

    $ export SINGULARITYENV_FS_LICENSE=$HOME/.freesurfer.txt
    $ singularity exec --cleanenv fmriprep.simg env | grep FS_LICENSE
    FS_LICENSE=/home/users/oesteban/.freesurfer.txt

As we can see, the export in the first line tells Singularity to set a
corresponding environment variable of the same name after dropping the
prefix ``SINGULARITYENV_``.

Accessing the host's filesystem
-------------------------------
Depending on how Singularity is configured on your cluster it might or might not
automatically bind (mount or expose) host folders to the container.
This is particularly relevant because, *if you can't run Singularity in privileged
mode* (which is almost certainly true in all the scenarios), **Singularity containers
are read only**.
This is to say that you won't be able to write *anything* unless Singularity can
access the host's filesystem in write mode.

By default, Singularity automatically binds (mounts) the user's *home* directory and
a *scratch* directory.
In addition, Singularity generally allows binding the necessary folders with
the ``-B <host_folder>:<container_folder>[:<permissions>]`` Singularity argument.
For example: ::

    $ singularity run --cleanenv -B /work:/work fmriprep.smig \
      /work/my_dataset/ /work/my_dataset/derivatives/fmriprep \
      participant \
      --participant-label 387 --nthreads 16 \
      --omp-nthreads 16

**Relevant aspects of the ``$HOME`` directory within the container**.
By default, Singularity will bind the user's ``$HOME`` directory in the host
into the ``/home/$USER`` (or equivalent) in the container.
Most of the times, it will also redefine the ``$HOME`` environment variable and
update it to point to the corresponding mount point in ``/home/$USER``.
However, these defaults can be overwritten in your system.
It is recommended to check your settings with your system's administrators.
If your Singularity installation allows it, you can workaround the ``$HOME``
specification combining the bind mounts argument (``-B``) with the home overwrite
argument (``--home``) as follows: ::

    $ singularity run -B $HOME:/home/fmriprep --home /home/fmriprep \
          --cleanenv fmriprep.simg <fmriprep arguments>

.. _singularity_tf:

*TemplateFlow* and Singularity
------------------------------
:ref:`TemplateFlow` is a helper tool that allows *fMRIPrep* (or any other neuroimaging workflow)
to programmatically access a repository of standard neuroimaging templates.
In other words, *TemplateFlow* allows *fMRIPrep* to dynamically change the templates that
are used, e.g., in the atlas-based brain extraction step or spatial normalization.

Default settings in the Singularity image should get along with the Singularity
installation of your system.
However, deviations from the default configurations of your installation may break
this compatibility.
A particularly problematic case arises when the home directory is mounted in the
container, but the ``$HOME`` environment variable is not correspondingly updated.
Typically, you will experience errors like ``OSError: [Errno 30] Read-only file system``
or ``FileNotFoundError: [Errno 2] No such file or directory: '/home/fmriprep/.cache'``.

If it is not explicitly forbidden in your installation, the first attempt to overcome this
issue is manually setting the ``$HOME`` directory as follows: ::

    $ singularity run --home $HOME --cleanenv fmriprep.simg <fmriprep arguments>

If the user's home directory is not automatically bound, then the second step would include
manually binding it as in the section above: ::

    $ singularity run -B $HOME:/home/fmriprep --home /home/fmriprep \
          --cleanenv fmriprep.simg <fmriprep arguments>

Finally, if the ``--home`` argument cannot be used, you'll need to provide the container with
writable filesystems where *TemplateFlow*'s files can be downloaded.
In addition, you will need to indicate *fMRIPrep* to update the default paths with the new mount
points setting the ``SINGULARITYENV_TEMPLATEFLOW_HOME`` variable. ::

    $ export SINGULARITYENV_TEMPLATEFLOW_HOME=/opt/templateflow  # Tell fMRIPrep the mount point
    $ singularity run -B <writable-path-on-host>:/opt/templateflow \
          --cleanenv fmriprep.simg <fmriprep arguments>

Internet access problems
------------------------
We have identified several conditions in which running *fMRIPrep* might fail because
of spotty or impossible access to Internet.

If your compute node cannot have access to Internet, then you'll need to make sure
you run *fMRIPrep* with the ``--notrack`` argument and pull down from TemplateFlow
all the resources that will be necessary.

If that is not the case (i.e., you should be able to hit HTTP/s endpoints), then
you can try the following:

``VerifiedHTTPSConnection ... Failed to establish a new connection: [Errno 110] Connection timed out``.
If you encounter an error like this, probably you'll need to set up an http proxy exporting
``SINGULARITYENV_http_proxy`` (see `\#1778 (comment)
<https://github.com/poldracklab/fmriprep/issues/1778#issuecomment-532297622>`__).
For example:
::

  $ export SINGULARITYENV_https_proxy=http://<ip or proxy name>:<port>

``requests.exceptions.SSLError: HTTPSConnectionPool ...``.
In this case, you container seems to be able to reach the Internet, but unable to use SSL
encription.
There are two potential solutions to the issue.
The `recommended one <https://neurostars.org/t/problems-using-pediatric-template-from-templateflow/4566/17>`__
is setting ``REQUESTS_CA_BUNDLE`` to the appropriate path, and/or binding
the appropriate filesystem:
::

  $ export SINGULARITYENV_REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
  $ singularity run -B <path-to-certs-folder>:/etc/ssl/certs \
        --cleanenv fmriprep.simg <fmriprep arguments>

Otherwise, `some users have succeeded pre-fetching the necessary templates onto
the TemplateFlow directory to then bind the folder at execution
<https://neurostars.org/t/problems-using-pediatric-template-from-templateflow/4566/15>`__:
::

  $ export TEMPLATEFLOW_HOME=/path/to/keep/templateflow
  $ python -m pip install -U templateflow  # Install the client
  $ python
  >>> import templateflow.api
  >>> templateflow.api.TF_S3_ROOT = 'http://templateflow.s3.amazonaws.com'
  >>> api.get(‘MNI152NLin6Asym’)

Finally, run the singularity image binding the appropriate folder:
::

  $ export SINGULARITYENV_TEMPLATEFLOW_HOME=/templateflow
  $ singularity run -B ${TEMPLATEFLOW_HOME:-$HOME/.cache/templateflow}:/templateflow \
        --cleanenv fmriprep.simg <fmriprep arguments>


Troubleshooting
---------------
Setting up a functional execution framework with Singularity might be tricky in some
:abbr:`HPC (high-performance computing)` systems.
Please make sure you have read the relevant `documentation of Singularity
<https://sylabs.io/docs/>`__, and checked all the defaults and configuration in your
system.
The next step is checking the environment and access to *fMRIPrep* resources, using
``singularity shell``.

  1. Check access to input data folder, and BIDS validity:
     ::

       $ singularity shell -B path/to/data:/data fmriprep.simg
       Singularity fmriprep.simg:~> ls /data
       CHANGES  README  dataset_description.json  participants.tsv  sub-01  sub-02  sub-03  sub-04  sub-05  sub-06  sub-07  sub-08  sub-09  sub-10  sub-11  sub-12  sub-13  sub-14  sub-15  sub-16  task-balloonanalogrisktask_bold.json
       Singularity fmriprep.simg:~> bids-validator /data
          1: [WARN] You should define 'SliceTiming' for this file. If you don't provide this information slice time correction will not be possible. (code: 13 - SLICE_TIMING_NOT_DEFINED)
                  ./sub-01/func/sub-01_task-balloonanalogrisktask_run-01_bold.nii.gz
                  ./sub-01/func/sub-01_task-balloonanalogrisktask_run-02_bold.nii.gz
                  ./sub-01/func/sub-01_task-balloonanalogrisktask_run-03_bold.nii.gz
                  ./sub-02/func/sub-02_task-balloonanalogrisktask_run-01_bold.nii.gz
                  ./sub-02/func/sub-02_task-balloonanalogrisktask_run-02_bold.nii.gz
                  ./sub-02/func/sub-02_task-balloonanalogrisktask_run-03_bold.nii.gz
                  ./sub-03/func/sub-03_task-balloonanalogrisktask_run-01_bold.nii.gz
                  ./sub-03/func/sub-03_task-balloonanalogrisktask_run-02_bold.nii.gz
                  ./sub-03/func/sub-03_task-balloonanalogrisktask_run-03_bold.nii.gz
                  ./sub-04/func/sub-04_task-balloonanalogrisktask_run-01_bold.nii.gz
                  ... and 38 more files having this issue (Use --verbose to see them all).
          Please visit https://neurostars.org/search?q=SLICE_TIMING_NOT_DEFINED for existing conversations about this issue.

  2. Check access to output data folder, and whether you have write permissions.
     ::

       $ singularity shell -B path/to/data/derivatives/fmriprep-1.5.0:/out fmriprep.simg
       Singularity fmriprep.simg:~> ls /out
       Singularity fmriprep.simg:~> touch /out/test
       Singularity fmriprep.simg:~> rm /out/test

  3. Check access and permissions to ``$HOME``:
     ::

       $ singularity shell fmriprep.simg
       Singularity fmriprep.simg:~> mkdir -p $HOME/.cache/testfolder
       Singularity fmriprep.simg:~> rmdir $HOME/.cache/testfolder

  4. Check *TemplateFlow* operation:
     ::

       $ singularity shell -B path/to/templateflow:/templateflow fmriprep.simg
       Singularity fmriprep.simg:~> echo ${TEMPLATEFLOW_HOME:-$HOME/.cache/templateflow}
       /home/users/oesteban/.cache/templateflow
       Singularity fmriprep.simg:~> python -c "from templateflow.api import get; get(['MNI152NLin2009cAsym', 'MNI152NLin6Asym', 'OASIS30ANTs', 'MNIPediatricAsym', 'MNIInfant'])"
         Downloading https://templateflow.s3.amazonaws.com/tpl-MNI152NLin6Asym/tpl-MNI152NLin6Asym_res-01_atlas-HOCPA_desc-th0_dseg.nii.gz
         304B [00:00, 1.28kB/s]
         Downloading https://templateflow.s3.amazonaws.com/tpl-MNI152NLin6Asym/tpl-MNI152NLin6Asym_res-01_atlas-HOCPA_desc-th25_dseg.nii.gz
         261B [00:00, 1.04kB/s]
         Downloading https://templateflow.s3.amazonaws.com/tpl-MNI152NLin6Asym/tpl-MNI152NLin6Asym_res-01_atlas-HOCPA_desc-th50_dseg.nii.gz
         219B [00:00, 867B/s]
         ...


Running Singularity on a SLURM system
-------------------------------------
An example of ``sbatch`` script to run *fMRIPrep* on a SLURM system with Singularity
available is given below: ::

    #!/bin/bash
    #
    #SBATCH -J fmriprep
    #SBATCH --array=1-36  # Replace indices with the right number of subjects
    #SBATCH --time=48:00:00
    #SBATCH -n 1
    #SBATCH --cpus-per-task=16
    #SBATCH --mem-per-cpu=4G
    #SBATCH -p queues,you,can,submit  # Partition names, separated by comma
    # Outputs ----------------------------------
    #SBATCH -o log/%x-%A-%a.out
    #SBATCH -e log/%x-%A-%a.err
    #SBATCH --mail-user=%u@domain.tld
    #SBATCH --mail-type=ALL
    # ------------------------------------------

    BIDS_DIR="$PROJECT/data/ds000109"
    DERIVS_DIR="derivatives/fmriprep-1.5.0"

    mkdir -p $HOME/.cache/templateflow
    mkdir -p ${BIDS_DIR}/${DERIVS_DIR}
    mkdir -p ${BIDS_DIR}/derivatives/freesurfer-6.0.1
    ln -s ${BIDS_DIR}/derivatives/freesurfer-6.0.1 ${BIDS_DIR}/${DERIVS_DIR}/freesurfer


    export SINGULARITYENV_FS_LICENSE=$HOME/.freesurfer.txt
    export SINGULARITYENV_TEMPLATEFLOW_HOME="/templateflow"
    SINGULARITY_CMD="singularity run --cleanenv -B $PROJECT:/project -B $HOME/.cache/templateflow:/templateflow -B $L_SCRATCH:/work $PROJECT/images/poldracklab_fmriprep_1.5.0-2019-09-10-6157fec3d0ea.simg"


    subject=$( sed -n -E "$((${SLURM_ARRAY_TASK_ID} + 1))s/sub-(\S*)\>.*/\1/gp" ${BIDS_DIR}/participants.tsv )
    cmd="${SINGULARITY_CMD} /project/data/ds000109 /project/data/ds000109/${DERIVS_DIR} participant --participant-label $subject -w /work/ -vv --omp-nthreads 8 --nthreads 12 --mem_mb 30000 --output-spaces MNI152NLin2009cAsym:res-2 anat fsnative fsaverage5 --cifti-output --use-aroma"

    # Setup done, run the command
    echo Running task ${SLURM_ARRAY_TASK_ID}
    echo Commandline: $cmd
    eval $cmd
    exitcode=$?

    # Output results to a table
    echo "sub-$subject   ${SLURM_ARRAY_TASK_ID}    $exitcode" \
          >> ${SLURM_JOB_NAME}.${SLURM_ARRAY_JOB_ID}.tsv
    echo Finished tasks ${SLURM_ARRAY_TASK_ID} with exit code $exitcode
    exit $exitcode

