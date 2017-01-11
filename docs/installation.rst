.. include:: links.rst

------------
Installation
------------

There are three ways to use fmriprep: in a `Docker Container`_, in a `Singularity Container`_, or in a `Manually Prepared Environment`_.
Using a container method is highly recommended.
Once you are ready to run fmriprep, see Usage_ for details.

Docker Container
================

Make sure command-line `Docker is installed <https://docs.docker.com/engine/installation/>`_.

See `External Dependencies`_ for more information (e.g., specific versions) on what is included in the fmriprep Docker image.

Now, assuming you have data, you can run fmriprep. You will need an active internet connection the first time. ::

    $ docker run --rm -v filepath/to/data/dir:/data:ro -v filepath/to/output/dir:/out -w /scratch poldracklab/fmriprep:latest /data /out/out participant

For example: ::

    $ docker run --rm -v $HOME/fullds005:/data:ro -v $HOME/dockerout:/out  -w /scratch poldracklab/fmriprep:latest /data /out/out participant -w /out/work/ -t ds005

Development environment
-----------------------
This section explains how to prepare a new development environment and
update an existing environment, as necessary.

Development in Docker is encouraged, for the sake of consistency and
portability.
By default, work should be built off of `poldracklab/fmriprep:latest
<https://hub.docker.com/r/poldracklab/fmriprep/>`_ (see above for
the basic procedure for running).

In order to test new code without rebuilding the Docker image, it is
possible to mount working repositories as source directories within the
container.
In the docker container, the following Python sources are kept in
``/root/src``: ::

    /root/src
    ├── fmriprep/
    ├── nipype/
    └── niworkflows/

To patch in working repositories, for instance contained in
``$HOME/projects/``, add the following arguments to your docker command: ::

    -v $HOME/projects/fmriprep:/root/src/fmriprep:ro
    -v $HOME/projects/niworkflows:/root/src/niworkflows:ro
    -v $HOME/projects/nipype:/root/src/nipype:ro

For example, ::

    $ docker run --rm -v $HOME/fullds005:/data:ro -v $HOME/dockerout:/out \
        -v $HOME/projects/fmriprep:/root/src/fmriprep:ro \
        poldracklab/fmriprep:latest /data /out/out participant \
        -w /out/work/ -t ds005

In order to work directly in the container, use ``--entrypoint=bash``, and
omit the fmriprep arguments: ::

    $ docker run --rm -v $HOME/fullds005:/data:ro -v $HOME/dockerout:/out \
        -v $HOME/projects/fmriprep:/root/src/fmriprep:ro --entrypoint=bash \
        poldracklab/fmriprep:latest

Preparing repository for patching
`````````````````````````````````
In order to patch a working repository into the docker image, its egg-info
must be built.
The first time this is done, the repository should be mounted read/write,
and be installed in editable mode.
For instance, to prepare to patch in fmriprep, niworkflows and nipype,
all located under ``$HOME/projects``, ::

    $ docker run --rm -it --entrypoint=bash \
        -v $HOME/projects/fmriprep:/root/src/fmriprep \
        -v $HOME/projects/niworkflows:/root/src/niworkflows \
        -v $HOME/projects/nipype:/root/src/nipype \
        poldracklab/fmriprep:latest
    root@03e5df018c5e:~# cd ~/src/fmriprep/
    root@03e5df018c5e:~/src/fmriprep# pip install -e .
    root@03e5df018c5e:~# cd ~/src/niworkflows/
    root@03e5df018c5e:~/src/niworkflows# pip install -e .
    root@03e5df018c5e:~# cd ~/src/nipype/
    root@03e5df018c5e:~/src/nipype# pip install -e .

Adding dependencies
```````````````````
New dependencies to insert into the Docker image will either be Python
or non-Python dependencies.
The image `must be rebuilt <#rebuilding-docker-image>`_ after any
dependency changes.

Python dependencies should generally be included in the ``REQUIRES``
list in `fmriprep/info.py
<https://github.com/poldracklab/fmriprep/blob/29133e5e9f92aae4b23dd897f9733885a60be311/fmriprep/info.py#L46-L61>`_.
If the latest version in `PyPI <https://pypi.org/>`_ is sufficient,
then no further action is required.

For large Python dependencies where there will be a benefit to
pre-compiled binaries, `conda <https://github.com/conda/conda>`_ packages
may be added to the ``conda install`` line in the `Dockerfile
<https://github.com/poldracklab/fmriprep/blob/29133e5e9f92aae4b23dd897f9733885a60be311/Dockerfile#L46>`_.

Finally, if a specific version of a repository needs to be pinned, edit
the ``requirements.txt`` file.
See the `current
<https://github.com/poldracklab/fmriprep/blob/master/requirements.txt>`_
file for examples.

Non-Python dependencies must also be installed in the Dockerfile, via a
``RUN`` command.
For example, installing an ``apt`` package may be done as follows: ::

    RUN apt-get update && \
        apt-get install -y <PACKAGE>

Rebuilding Docker image
```````````````````````
If it is necessary to rebuild the Docker image, a local image named
``fmriprep`` may be built from within the working fmriprep
repository, located in ``~/projects/fmriprep``: ::

    ~/projects/fmriprep$ docker build -t fmriprep .

To work in this image, replace ``poldracklab/fmriprep:latest`` with
``fmriprep`` in any of the above commands.

Singularity Container
=====================

For security reasons, many HPCs (e.g., TACC) do not allow Docker containers, but do allow `Singularity <https://github.com/singularityware/singularity>`_ containers.
In this case, start with a machine (e.g., your personal computer) with Docker installed.
Use `docker2singularity <https://github.com/singularityware/docker2singularity>`_ to create a singularity image. You will need an active internet connection and some time. ::

    $ docker run -v /var/run/docker.sock:/var/run/docker.sock -v D:\host\path\where\to\ouptut\singularity\image:/output --privileged -t --rm singularityware/docker2singularity poldracklab/fmriprep:latest

Transfer the resulting Singularity image to the HPC, for example, using ``scp``. ::

    $ scp poldracklab_fmriprep_latest-*.img  user@hcpserver.edu:/path/to/downloads

If the data to be preprocessed is also on the HPC, you are ready to run fmriprep. ::

    $ singularity run path/to/singularity/image.img --participant_label label  path/to/data/dir path/to/output/dir participant

For example: ::

    $ singularity run ~/poldracklab_fmriprep_latest-2016-12-04-5b74ad9a4c4d.img --participant_label sub-387 --nthreads 1 -w $WORK/lonestar/work --ants-nthreads 16 --skull--strip-ants /work/04168/asdf/lonestar/ $WORK/lonestar/output participant


Manually Prepared Environment
=============================

.. note::

   This method is not recommended! Make sure you would rather do this than use a `Docker Container`_ or a `Singularity Container`_.

Make sure all of fmriprep's `External Dependencies`_ are installed.
These tools must be installed and their binaries available in the
system's ``$PATH``.

If you have pip installed, install fmriprep ::

    $ pip install fmriprep

If you have your data on hand, you are ready to run fmriprep: ::

    $ fmriprep data/dir output/dir --participant_label sub-num participant

External Dependencies
=====================

``fmriprep`` is implemented using nipype_, but it requires some other neuroimaging
software tools:

- `FSL <http://fsl.fmrib.ox.ac.uk/fsl/fslwiki/>`_ (version 5.0)
- `ANTs <http://stnava.github.io/ANTs/>`_ (version 2.1.0.Debian-Ubuntu_X64)
- `AFNI <https://afni.nimh.nih.gov/>`_ (version Debian-16.2.07)
- `FreeSurfer <https://surfer.nmr.mgh.harvard.edu/>`_ (version Linux-centos4_x86_64-stable-pub-v5.3.0-HCP)
- `C3D <https://sourceforge.net/projects/c3d/>`_ (version 1.0.0)
