from catalyst.version import __version__
from catalyst.monster import CatalystMonster


def test_v5_release_metadata():
    assert __version__ == '5.7.0'
    assert CatalystMonster.release_protocol == 'catalyst.monster.v5.5'
    assert CatalystMonster.apex_protocol == 'catalyst.apex-runtime.v3'
