"""Check the configuration module and file."""
from pathlib import Path
from pkg_resources import resource_filename as pkgrf
import pytest
from toml import loads
from niworkflows.utils.spaces import format_reference

from .. import config


def test_config_spaces():
    """Check that all necessary spaces are recorded in the config."""
    filename = Path(pkgrf('fmriprep', 'data/tests/config.toml'))
    settings = loads(filename.read_text())
    for sectionname, configs in settings.items():
        if sectionname != 'environment':
            section = getattr(config, sectionname)
            section.load(configs, init=False)
    config.nipype.init()
    config.loggers.init()
    config.init_spaces()

    spaces = config.workflow.spaces
    assert "MNI152NLin6Asym:res-2" not in [
        str(s) for s in spaces.get_standard(full_spec=True)]

    assert "MNI152NLin6Asym_res-2" not in [
        format_reference((s.fullname, s.spec))
        for s in spaces.references if s.standard and s.dim == 3
    ]

    config.workflow.use_aroma = True
    config.init_spaces()
    spaces = config.workflow.spaces

    assert "MNI152NLin6Asym:res-2" in [
        str(s) for s in spaces.get_standard(full_spec=True)]

    assert "MNI152NLin6Asym_res-2" in [
        format_reference((s.fullname, s.spec))
        for s in spaces.references if s.standard and s.dim == 3
    ]

    config.execution.output_spaces = None
    config.workflow.use_aroma = False
    config.init_spaces()
    spaces = config.workflow.spaces

    assert [str(s) for s in spaces.get_standard(full_spec=True)] == []

    assert [
        format_reference((s.fullname, s.spec))
        for s in spaces.references if s.standard and s.dim == 3
    ] == ['MNI152NLin2009cAsym']


@pytest.mark.parametrize("master_seed,ants_seed,numpy_seed", [
    (1, 17612, 8272), (100, 19094, 60232)
])
def test_prng_seed(master_seed, ants_seed, numpy_seed):
    """Ensure seeds are properly tracked"""
    import os

    seeds = config.seeds
    seeds.load({'_random_seed': master_seed})
    seeds.init()
    assert seeds.master == master_seed
    assert seeds.ants == ants_seed
    assert seeds.numpy == numpy_seed
    assert os.getenv("ANTS_RANDOM_SEED") == str(ants_seed)
