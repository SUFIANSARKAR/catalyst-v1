from catalyst import __version__
from catalyst.capabilities import manifest

def test_v360_version_and_capabilities():
    assert tuple(map(int, __version__.split('.'))) >= (3, 14, 0)
