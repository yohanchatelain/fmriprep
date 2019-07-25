"""Test CLI."""
from packaging.version import Version
import pytest
from .. import _version
from ... import __about__
from ..run import get_parser


@pytest.mark.parametrize(('current', 'latest'), [
    ('1.0.0', '1.3.2'),
    ('1.3.2', '1.3.2')
])
def test_get_parser_update(monkeypatch, capsys, current, latest):
    """Make sure the out-of-date banner is shown."""
    expectation = Version(current) < Version(latest)

    def _mock_check_latest(*args, **kwargs):
        return Version(latest)

    monkeypatch.setattr(__about__, '__version__', current)
    monkeypatch.setattr(_version, 'check_latest', _mock_check_latest)

    get_parser()
    captured = capsys.readouterr().err

    msg = """\
WARNING: The current version of fMRIPrep (%s) is outdated.
Please consider upgrading to the latest version %s.
Before upgrading, please consider that mixing fMRIPrep versions
within a single study is strongly discouraged.""" % (current, latest)

    assert (msg in captured) is expectation


@pytest.mark.parametrize('flagged', [
    (True, None),
    (True, 'random reason'),
    (False, None),
])
def test_get_parser_blacklist(monkeypatch, capsys, flagged):
    """Make sure the blacklisting banner is shown."""
    def _mock_is_bl(*args, **kwargs):
        return flagged

    monkeypatch.setattr(_version, 'is_flagged', _mock_is_bl)

    get_parser()
    captured = capsys.readouterr().err

    assert ('FLAGGED' in captured) is flagged[0]
    if flagged[0]:
        assert ((flagged[1] or 'reason: unknown') in captured)
