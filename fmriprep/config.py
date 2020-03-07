# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
r"""
*fMRIPrep* settings.

This module implements the memory structures to keep a consistent, singleton config.

Example
-------

.. code-block:: Python

    from fmriprep import config
    config_file = config.execution.work_dir / '.fmriprep.toml'
    config.to_filename(config_file)
    # Call build_workflow(config_file, retval) in a subprocess
    with Manager() as mgr:
        from .workflow import build_workflow
        retval = mgr.dict()
        p = Process(target=build_workflow, args=(str(config_file), retval))
        p.start()
        p.join()
    config.load(config_file)
    # Access configs from any code section as:
    value = config.section.setting

The module also has a :py:func:`to_filename` function to allow writting out
the settings to hard disk in *ToML* format, which looks like

.. code-block:: toml

    [environment]
    cpu_count = 8
    exec_env = "posix"
    free_mem = 2.2
    overcommit_policy = "heuristic"
    overcommit_limit = "50%"
    nipype_version = "1.5.0"
    templateflow_version = "0.4.2"
    version = "20.0.1"

    [nipype]
    crashfile_format = "txt"
    get_linked_libs = false
    nprocs = 8
    omp_nthreads = 8
    plugin = "MultiProc"
    resource_monitor = false
    stop_on_first_crash = false

    [execution]
    bids_dir = "/data/openfmri/ds000005"
    boilerplate_only = false
    exec_env = "posix"
    fs_license_file = "/opt/freesurfer/license.txt"
    fs_subjects_dir = "/data/openfmri/ds000005/derivatives/freesurfer-6.0.1"
    log_dir = "/data/openfmri/ds000005/derivatives/fmriprep/logs"
    log_level = 15
    low_mem = false
    md_only_boilerplate = false
    notrack = true
    output_dir = "/data/openfmri/ds000005/derivatives"
    reports_only = false
    run_uuid = "20200302-174345_9ba9f304-82de-4538-8c3a-570c5f5d8f2f"
    participant_label = [ "01",]
    work_dir = "work/"
    write_graph = false

    [workflow]
    anat_only = false
    aroma_err_on_warn = false
    aroma_melodic_dim = -200
    bold2t1w_dof = 6
    cifti_output = false
    fmap_bspline = false
    force_syn = false
    hires = true
    ignore = []
    internal_spaces = "MNI152NLin2009cAsym"
    longitudinal = false
    medial_surface_nan = false
    run_reconall = true
    skull_strip_fixed_seed = false
    skull_strip_template = "OASIS30ANTs"
    t2s_coreg = false
    use_aroma = false

    [nipype.plugin_args]
    maxtasksperchild = 1
    raise_insufficient = false

This config file is used to pass the settings across processes,
using the :py:func:`load` function.

Other responsibilities of the config module:

  * Switching Python's ``multiprocessing`` to *forkserver* mode.
  * Set up new logger levels (25: IMPORTANT, and 15: VERBOSE).
  * Set up a warnings filter as soon as possible.
  * Initialize runtime descriptive settings (e.g., default FreeSurfer license,
    execution environment, nipype and *fMRIPrep* versions, etc.).
  * Automated I/O magic operations:

    * :obj:`Path` \<-\> :obj:`str` \<-\> :obj:`Path`).
    * :py:class:`~niworkflows.util.spaces.SpatialReferences` \<-\> :obj:`str` \<-\>
      :py:class:`~niworkflows.util.spaces.SpatialReferences`
    * :py:class:`~bids.layout.BIDSLayout` \<-\> :obj:`str` \<-\>
      :py:class:`~bids.layout.BIDSLayout`

"""
from multiprocessing import set_start_method
import warnings

# cmp is not used by fmriprep, so ignore nipype-generated warnings
warnings.filterwarnings('ignore', 'cmp not installed')
warnings.filterwarnings('ignore', 'This has not been fully tested. Please report any failures.')
warnings.filterwarnings('ignore', "can't resolve package from __spec__ or __package__")
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=ResourceWarning)


try:
    set_start_method('forkserver')
except RuntimeError:
    pass  # context has been already set
finally:
    # Defer all custom import for after initializing the forkserver and
    # redirecting warnings
    import os
    import sys
    import logging

    from uuid import uuid4
    from pathlib import Path
    from time import strftime
    from niworkflows.utils.spaces import SpatialReferences as _SRs, Reference as _Ref
    from nipype import logging as nlogging, __version__ as _nipype_ver
    from templateflow import __version__ as _tf_ver
    from . import __version__


def redirect_warnings(message, category, filename, lineno, file=None, line=None):
    """Redirect other warnings."""
    logger = logging.getLogger()
    logger.debug('Captured warning (%s): %s', category, message)


warnings.showwarning = redirect_warnings

logging.addLevelName(25, 'IMPORTANT')  # Add a new level between INFO and WARNING
logging.addLevelName(15, 'VERBOSE')  # Add a new level between INFO and DEBUG

DEFAULT_MEMORY_MIN_GB = 0.01

_exec_env = os.name
_docker_ver = None
# special variable set in the container
if os.getenv('IS_DOCKER_8395080871'):
    _exec_env = 'singularity'
    _cgroup = Path('/proc/1/cgroup')
    if _cgroup.exists() and 'docker' in _cgroup.read_text():
        _docker_ver = os.getenv('DOCKER_VERSION_8395080871')
        _exec_env = 'fmriprep-docker' if _docker_ver else 'docker'
    del _cgroup

_fs_license = os.getenv('FS_LICENSE')
if _fs_license is None and os.getenv('FREESURFER_HOME'):
    _fs_license = os.path.join(os.getenv('FREESURFER_HOME'), 'license.txt')

_templateflow_home = Path(os.getenv(
    'TEMPLATEFLOW_HOME',
    os.path.join(os.getenv('HOME'), '.cache', 'templateflow'))
)

try:
    from psutil import virtual_memory
    _free_mem_at_start = round(virtual_memory().free / 1024**3, 1)
except Exception:
    _free_mem_at_start = None

_oc_limit = 'n/a'
_oc_policy = 'n/a'
try:
    # Memory policy may have a large effect on types of errors experienced
    _proc_oc_path = Path('/proc/sys/vm/overcommit_memory')
    if _proc_oc_path.exists():
        _oc_policy = {
            '0': 'heuristic', '1': 'always', '2': 'never'
        }.get(_proc_oc_path.read_text().strip(), 'unknown')
        if _oc_policy != 'never':
            _proc_oc_kbytes = Path('/proc/sys/vm/overcommit_kbytes')
            if _proc_oc_kbytes.exists():
                _oc_limit = _proc_oc_kbytes.read_text().strip()
            if _oc_limit in ('0', 'n/a') and Path('/proc/sys/vm/overcommit_ratio').exists():
                _oc_limit = '{}%'.format(
                    Path('/proc/sys/vm/overcommit_ratio').read_text().strip()
                )
except Exception:
    pass


class _Config:
    """An abstract class forbidding instantiation."""

    _paths = tuple()

    def __init__(self):
        """Avert instantiation."""
        raise RuntimeError('Configuration type is not instantiable.')

    @classmethod
    def load(cls, settings):
        """Store settings from a dictionary."""
        for k, v in settings.items():
            if v is None:
                continue
            if k in cls._paths:
                setattr(cls, k, Path(v).absolute())
                continue
            if hasattr(cls, k):
                setattr(cls, k, v)

    @classmethod
    def get(cls):
        """Return defined settings."""
        out = {}
        for k, v in cls.__dict__.items():
            if k.startswith('_') or v is None:
                continue
            if callable(getattr(cls, k)):
                continue
            if k in cls._paths:
                v = str(v)
            if isinstance(v, _SRs):
                v = ' '.join([str(s) for s in v.references]) or None
            if isinstance(v, _Ref):
                v = str(v) or None
            out[k] = v
        return out


class environment(_Config):
    """Read-only options."""

    cpu_count = os.cpu_count()
    """Number of available CPUs."""
    exec_docker_version = _docker_ver
    """Version of Docker Engine."""
    exec_env = _exec_env
    """A string representing the execution platform."""
    free_mem = _free_mem_at_start
    """Free memory at start."""
    overcommit_policy = _oc_policy
    """Linux's kernel virtual memory overcommit policy."""
    overcommit_limit = _oc_limit
    """Linux's kernel virtual memory overcommit limits."""
    nipype_version = _nipype_ver
    """Nipype's current version."""
    templateflow_version = _tf_ver
    """The TemplateFlow client version installed."""
    version = __version__
    """*fMRIPrep*'s version."""


class nipype(_Config):
    """Nipype configuration."""

    crashfile_format = 'txt'
    """The file format for crashfiles, either text or pickle."""
    get_linked_libs = False
    """Run NiPype's tool to enlist linked libraries for every interface."""
    memory_gb = None
    """Estimation in GB of the RAM this workflow can allocate at any given time."""
    nprocs = os.cpu_count()
    """Number of processes (compute tasks) that can be run in parallel (multiprocessing only)."""
    omp_nthreads = os.cpu_count()
    """Number of CPUs a single process can access for multithreaded execution."""
    plugin = 'MultiProc'
    """NiPype's execution plugin."""
    plugin_args = {
        'maxtasksperchild': 1,
        'raise_insufficient': False,
    }
    """Settings for NiPype's execution plugin."""
    resource_monitor = False
    """Enable resource monitor."""
    stop_on_first_crash = True
    """Whether the workflow should stop or continue after the first error."""

    @classmethod
    def get_plugin(cls):
        """Format a dictionary for Nipype consumption."""
        out = {
            'plugin': cls.plugin,
            'plugin_args': cls.plugin_args,
        }
        if cls.plugin in ('MultiProc', 'LegacyMultiProc'):
            out['plugin_args']['nprocs'] = int(cls.nprocs)
            if cls.memory_gb:
                out['plugin_args']['memory_gb'] = float(cls.memory_gb)
        return out


class execution(_Config):
    """Configure workflow-level settings."""

    bids_dir = None
    """An existing path to the dataset, which must be BIDS-compliant."""
    bids_description_hash = None
    """Checksum (SHA256) of the ``dataset_description.json`` of the BIDS dataset."""
    bids_filters = None
    """A dictionary of BIDS selection filters."""
    boilerplate_only = False
    """Only generate a boilerplate."""
    debug = False
    """Run in sloppy mode (meaning, suboptimal parameters that minimize run-time)."""
    echo_idx = None
    """Select a particular echo for multi-echo EPI datasets."""
    fs_license_file = _fs_license
    """An existing file containing a FreeSurfer license."""
    fs_subjects_dir = None
    """FreeSurfer's subjects directory."""
    layout = None
    """The path to the exported index of a py:class:`~bids.layout.BIDSLayout` object."""
    log_dir = None
    """The path to a directory that contains execution logs."""
    log_level = 25
    """Output verbosity."""
    low_mem = None
    """Utilize uncompressed NIfTIs and other tricks to minimize memory allocation."""
    md_only_boilerplate = False
    """Do not convert boilerplate from MarkDown to LaTex and HTML."""
    notrack = False
    """Do not monitor *fMRIPrep* using Sentry.io."""
    output_dir = None
    """Folder where derivatives will be stored."""
    output_spaces = None
    """List of (non)standard spaces designated as spatial references for outputs."""
    reports_only = False
    """Only build the reports, based on the reportlets found in a cached working directory."""
    run_uuid = '%s_%s' % (strftime('%Y%m%d-%H%M%S'), uuid4())
    """Unique identifier of this particular run."""
    participant_label = None
    """List of participant identifiers that are to be preprocessed."""
    task_id = None
    """Select a particular task from all available in the dataset."""
    templateflow_home = _templateflow_home
    """The root folder of the TemplateFlow client."""
    work_dir = Path('work').absolute()
    """Path to a working directory where intermediate results will be available."""
    write_graph = False
    """Write out the computational graph corresponding to the planned preprocessing."""

    _layout = None

    _paths = (
        'bids_dir',
        'fs_license_file',
        'fs_subjects_dir',
        'layout',
        'log_dir',
        'output_dir',
        'templateflow_home',
        'work_dir',
    )


# These variables are not necessary anymore
del _fs_license
del _exec_env
del _nipype_ver
del _templateflow_home
del _tf_ver
del _free_mem_at_start
del _oc_limit
del _oc_policy


class workflow(_Config):
    """Configure anatomical workflow."""

    anat_only = False
    """Execute the anatomical preprocessing only."""
    aroma_err_on_warn = None
    """Cast AROMA warnings to errors."""
    aroma_melodic_dim = None
    """Number of ICA components to be estimated by MELODIC
    (positive = exact, negative = maximum)."""
    bold2t1w_dof = None
    """Degrees of freedom of the BOLD-to-T1w registration steps."""
    cifti_output = None
    """Generate HCP Grayordinates, accepts either ``'91k'`` (default) or ``'170k'``."""
    dummy_scans = None
    """Set a number of initial scans to be considered nonsteady states."""
    fmap_bspline = None
    """Regularize fieldmaps with a field of B-Spline basis."""
    fmap_demean = None
    """Remove the mean from fieldmaps."""
    force_syn = None
    """Run *fieldmap-less* susceptibility-derived distortions estimation."""
    hires = None
    """Run FreeSurfer ``recon-all`` with the ``-hires`` flag."""
    ignore = None
    """Ignore particular steps for *fMRIPrep*."""
    internal_spaces = None
    """Standard and nonstandard spaces."""
    longitudinal = False
    """Run FreeSurfer ``recon-all`` with the ``-logitudinal`` flag."""
    medial_surface_nan = None
    """Fill medial surface with NaNs (not-a-number) when sampling."""
    regressors_all_comps = None
    regressors_dvars_th = None
    regressors_fd_th = None
    run_reconall = True
    """Run FreeSurfer's surface reconstruction."""
    skull_strip_fixed_seed = False
    """Fix a seed for skull-stripping."""
    skull_strip_template = 'OASIS30ANTs'
    """Change default brain extraction template."""
    spaces = None
    """Standard and nonstandard spaces."""
    t2s_coreg = None
    r"""Co-register echos before generating the T2\* reference of ME-EPI."""
    use_aroma = None
    """Run ICA-AROMA."""
    use_bbr = None
    """Run boundary-based registration for BOLD-to-T1w registration (default: ``True``)."""
    use_syn = None
    """Run *fieldmap-less* susceptibility-derived distortions estimation
    in the absence of any alternatives."""


class loggers(_Config):
    """Configure loggers."""

    _fmt = "%(asctime)s,%(msecs)d %(name)-2s " "%(levelname)-2s:\n\t %(message)s"
    _datefmt = "%y%m%d-%H:%M:%S"

    default = logging.getLogger()
    cli = logging.getLogger('cli')
    workflow = nlogging.getLogger('nipype.workflow')
    interface = nlogging.getLogger('nipype.interface')
    utils = nlogging.getLogger('nipype.utils')


def from_dict(settings):
    """Read settings from a flat dictionary."""
    nipype.load(settings)
    execution.load(settings)
    workflow.load(settings)
    set_logger_level()


def load(filename):
    """Load settings from file."""
    from toml import loads
    filename = Path(filename)
    settings = loads(filename.read_text())
    for sectionname, configs in settings.items():
        if sectionname != 'environment':
            section = getattr(sys.modules[__name__], sectionname)
            section.load(configs)
    set_logger_level()
    init_spaces()
    init_layout()


def get(flat=False):
    """Get config as a dict."""
    settings = {
        'environment': environment.get(),
        'execution': execution.get(),
        'workflow': workflow.get(),
        'nipype': nipype.get(),
    }
    if not flat:
        return settings

    return {'.'.join((section, k)): v
            for section, configs in settings.items()
            for k, v in configs.items()}


def dumps():
    """Format config into toml."""
    from toml import dumps
    return dumps(get())


def to_filename(filename):
    """Write settings to file."""
    filename = Path(filename)
    filename.write_text(dumps())


def init_layout():
    """Init a new layout."""
    if execution._layout is None:
        import re
        from bids.layout import BIDSLayout
        work_dir = execution.work_dir / 'bids.db'
        work_dir.mkdir(exist_ok=True, parents=True)
        execution._layout = BIDSLayout(
            str(execution.bids_dir),
            validate=False,
            # database_path=str(work_dir),
            ignore=("code", "stimuli", "sourcedata", "models",
                    "derivatives", re.compile(r'^\.')))
    execution.layout = execution._layout


def set_logger_level():
    """Set the current log level to all nipype loggers."""
    _handler = logging.StreamHandler(stream=sys.stdout)
    _handler.setFormatter(
        logging.Formatter(fmt=loggers._fmt, datefmt=loggers._datefmt)
    )
    loggers.cli.addHandler(_handler)
    loggers.default.setLevel(execution.log_level)
    loggers.cli.setLevel(execution.log_level)
    loggers.interface.setLevel(execution.log_level)
    loggers.workflow.setLevel(execution.log_level)
    loggers.utils.setLevel(execution.log_level)


def init_spaces(checkpoint=True):
    """Get a spatial references."""
    from niworkflows.utils.spaces import Reference, SpatialReferences
    if (
        getattr(workflow, 'spaces')
        and isinstance(workflow.spaces, SpatialReferences)
    ):
        return

    spaces = execution.output_spaces
    if spaces is not None and not isinstance(spaces, _SRs):
        spaces = SpatialReferences(
            [ref for s in execution.output_spaces.split(' ')
             for ref in Reference.from_string(s)]
        )
    if spaces is None:
        spaces = _SRs()

    if checkpoint:
        spaces.checkpoint()

    if workflow.internal_spaces:
        internal = [
            Reference.from_string(ref)
            for ref in workflow.internal_spaces.strip().split(' ')
        ]
        spaces += [
            ref[0] for ref in internal if ref[0].fullname not in spaces
        ]
    workflow.spaces = spaces
