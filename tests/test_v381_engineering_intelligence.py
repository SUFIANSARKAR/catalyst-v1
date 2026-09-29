from pathlib import Path
from catalyst.engineering import EngineeringIntelligenceFabric, EngineeringCatalog


def test_catalog_contains_supplied_engineering_sources(tmp_path):
    ids = {x['id'] for x in EngineeringCatalog.list_sources()}
    assert {'physicsnemo', 'pyvista'} <= ids


def test_recommendation_is_dependency_neutral(tmp_path):
    fabric = EngineeringIntelligenceFabric(str(tmp_path), str(tmp_path / 'data'))
    result = fabric.recommend('CFD mesh thermal engineering design')
    assert result['recommendation']['id'] in {'physicsnemo', 'pyvista'}
    assert result['note']


def test_status_does_not_require_heavy_runtimes(tmp_path):
    fabric = EngineeringIntelligenceFabric(str(tmp_path), str(tmp_path / 'data'))
    status = fabric.status()
    assert status['protocol'] == 'catalyst.engineering.v1'
    assert len(status['runtimes']) == 2


def test_geometry_path_is_contained(tmp_path):
    fabric = EngineeringIntelligenceFabric(str(tmp_path), str(tmp_path / 'data'))
    outside = tmp_path.parent / 'outside.mesh'
    outside.write_text('x')
    try:
        fabric.inspect_geometry(str(outside))
    except PermissionError:
        pass
    else:
        raise AssertionError('path escape was not blocked')
