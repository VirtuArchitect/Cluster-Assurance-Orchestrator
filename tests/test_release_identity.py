import json
from pathlib import Path
from app.version import VERSION, build_identity
from app.services.evidence_manifest import latest_manifest


def test_unknown_build_is_not_clean_or_approved():
    build = build_identity()
    assert build['version'] == VERSION
    assert build['production_approved'] is False
    if not Path('backend/app/build-info.json').exists():
        assert build['source_state'] == 'unknown'
        assert build['revision'] == 'unknown'


def test_manifest_retains_saved_version_not_running_release(tmp_path):
    file = tmp_path / 'inventory-run-20260101.json'
    data = {'run_id': 'synthetic', 'collectors': [], 'clusters': [], 'build': {'version': '0.1.0'}}
    file.write_text(json.dumps(data))
    assert latest_manifest(tmp_path).product_version == '0.1.0'
    del data['build']
    file.write_text(json.dumps(data))
    assert latest_manifest(tmp_path).product_version == 'unknown (legacy evidence)'


def test_canonical_package_versions_agree():
    root = Path(__file__).resolve().parents[1]
    for file in ['frontend/package.json', 'frontend/package-lock.json']:
        assert json.loads((root / file).read_text())['version'] == VERSION


def test_new_collection_stores_producer_identity(tmp_path):
    from app.domain.inventory import InventoryRunReport
    from app.services.inventory_run import write_inventory_evidence
    report = InventoryRunReport(run_id='synthetic', read_only=True, ncc_enabled=False,
                                ssh_enabled=False, collectors=[], observations=[])
    path = write_inventory_evidence(report, tmp_path)
    saved = json.loads(path.read_text())
    assert saved['build'] == build_identity()
    assert latest_manifest(tmp_path).product_version == VERSION


def test_health_exposes_build_and_effective_mode(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core.config import Settings
    client = TestClient(create_app(Settings(admin_db_path=str(tmp_path / 'admin.sqlite3'),
                                           evidence_dir=str(tmp_path), demo_mode=True)))
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    assert response.json()['build'] == build_identity()
    assert response.json()['readOnlyMode'] is True
