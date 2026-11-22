from dataclasses import replace
from datetime import datetime, UTC
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import MagicMock, patch
import pytest
from app.core.config import Settings
from app.services import monitoring_control as control
from app.services.process_lock import FileLock
from app.services.alerting import evidence_is_trustworthy

@pytest.fixture
def settings(tmp_path):
    return Settings(evidence_dir=str(tmp_path),demo_mode=False,monitoring_enabled=True,
                    enable_alerts=True,alert_webhook_url='http://127.0.0.1:12345/hook',alert_max_attempts=2)

def report(now=1000,complete=True,tls='strict'):
    return {'generated_at':datetime.fromtimestamp(now,UTC).isoformat(),'status':'COLLECTED',
            'read_only':True,'run_id':'synthetic','tls_mode':tls,
            'collectors':[{'source':'prism-central','kind':'alerts','complete':complete}],
            'incidents':[{'id':'synthetic','check_id':'test-check','source':'prism-central',
                          'availability':'CURRENT','resolved':False,'severity':'CRITICAL'}]}

def rows(settings):
    with control.connect(settings) as db:return [dict(row) for row in db.execute('SELECT * FROM deliveries ORDER BY created')]

def save(settings,data):
    from pathlib import Path
    (Path(settings.evidence_dir)/'monitoring-run-synthetic.json').write_text(json.dumps(data))

def test_outbox_is_durable_deduplicated_and_retries_same_identity(settings):
    control.transition(settings,'collector:pc','FAILED',{'kind':'collector'},1000)
    control.transition(settings,'collector:pc','FAILED',{'kind':'collector'},1001)
    assert len(rows(settings))==1
    identity=rows(settings)[0]['id']
    def fail(*args):raise OSError('secret should never be retained')
    control.send_due(settings,fail,1001)
    assert rows(settings)[0]['status']=='PENDING'
    assert rows(settings)[0]['last_error']=='OSError'
    sender=MagicMock()
    control.send_due(settings,sender,1010);sender.assert_not_called()
    control.send_due(settings,sender,1017)
    assert sender.call_args.args[2]==identity
    assert rows(settings)[0]['status']=='DELIVERED'
    assert rows(settings)[0]['attempts']==2

def test_dead_delivery_and_worker_heartbeat_are_visible(settings):
    control.transition(settings,'collector:pc','FAILED',{'kind':'collector'},1000)
    def fail(*_):raise RuntimeError()
    control.send_due(settings,fail,1000);control.send_due(settings,fail,1020)
    control.stamp(settings,collector_heartbeat=1020,sender_heartbeat=1020)
    assert control.worker_status(settings,1021)['status']=='DEGRADED'
    assert control.worker_status(settings,1300)['status']=='UNHEALTHY'
    assert control.worker_status(settings,1021)['queue']['DEAD']==1

def test_fresh_complete_tls_gate_and_recovery_cannot_be_inferred(settings):
    for data in [report(700),report(1001),report(1000,False),report(1000,tls='insecure_skip_verify')]:
        control.process_report(settings,data,1000)
    assert all(json.loads(row['payload'])['kind']=='collector' for row in rows(settings))
    fresh=report();control.process_report(settings,fresh,1000)
    incident_rows=[r for r in rows(settings) if json.loads(r['payload'])['kind']=='incident']
    assert len(incident_rows)==1
    stale=report(700);save(settings,stale);sender=MagicMock()
    # Superseded collector notices may exist; isolate the infrastructure message.
    with control.connect(settings) as db:db.execute("UPDATE deliveries SET status='DELIVERED' WHERE id!=?",(incident_rows[0]['id'],))
    control.send_due(settings,sender,1001);sender.assert_not_called()
    assert rows(settings)[-1]['last_error']=='EvidenceGate'

def test_resolved_a200335_remains_recovery_unverified(settings):
    data=report();data['incidents'][0].update(check_id='A200335',resolved=True)
    control.process_report(settings,data,1000)
    assert json.loads(rows(settings)[0]['payload'])['state']=='RECOVERY_UNVERIFIED'

def test_failure_then_recovery_supersedes_undelivered_failure(settings):
    control.transition(settings,'collector:pc','FAILED',{'kind':'collector'},1000)
    control.transition(settings,'collector:pc','CLEAR',{'kind':'collector'},1001)
    assert [r['status'] for r in rows(settings)]==['SUPERSEDED','PENDING']

def test_destination_changes_never_redirect_queued_data(settings):
    control.transition(settings,'collector:pc','FAILED',{'kind':'collector'},1000)
    sender=MagicMock();changed=replace(settings,alert_webhook_url='https://different.example.invalid/')
    control.send_due(changed,sender,1001);sender.assert_not_called()
    assert rows(settings)[0]['status']=='DEAD'

def test_unattended_collection_forces_read_only_and_keeps_inventory_failure(settings):
    store=MagicMock();store.inventory_settings_from_connections.return_value=replace(settings,read_only_mode=False,enable_ssh=True,enable_ncc=True)
    def collect(effective):
        assert effective.read_only_mode and not effective.enable_ssh and not effective.enable_ncc
        return report(__import__('time').time())
    def inventory(_):raise ValueError('sensitive raw error')
    control.collect_once(settings,store,collect,inventory)
    state=control.worker_status(settings)['state']
    assert state['inventory_error']=='ValueError'
    assert state['last_success_at']

def test_singleton_lock_prevents_two_collectors(tmp_path):
    one=FileLock(tmp_path/'lock');two=FileLock(tmp_path/'lock')
    assert one.acquire();assert not two.acquire();one.release()
    assert two.acquire();two.release()

def test_real_http_retry_uses_same_idempotency_key(settings):
    seen=[]
    class Sink(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append(self.headers['Idempotency-Key']);self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(503 if len(seen)==1 else 204);self.end_headers()
        def log_message(self,*_):pass
    server=HTTPServer(('127.0.0.1',0),Sink);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        configured=replace(settings,alert_webhook_url=f'http://127.0.0.1:{server.server_port}/hook')
        control.transition(configured,'collector:pc','FAILED',{'kind':'collector'},1000)
        control.send_due(configured,now=1000);control.send_due(configured,now=1020)
        assert len(seen)==2 and seen[0]==seen[1]
        assert rows(settings)[0]['status']=='DELIVERED'
    finally:server.shutdown();server.server_close();thread.join()

def test_smtp_uses_tls_and_stable_message_id(settings):
    configured=replace(settings,smtp_host='smtp.example.invalid',smtp_from='monitor@example.invalid',alert_email_to='ops@example.invalid')
    with patch('app.services.monitoring_control.smtplib.SMTP') as factory:
        smtp=factory.return_value.__enter__.return_value;smtp.send_message.return_value={}
        control.deliver(configured,'email','stable-id',{'kind':'collector','state':'FAILED'})
        smtp.starttls.assert_called_once()
        assert smtp.send_message.call_args.args[0]['Message-ID']=='<stable-id@cluster-assurance.invalid>'

def test_old_inventory_trust_gate_rejects_stale_partial_and_missing_tls(settings):
    data={'available':True,'age_seconds':30,'tls_mode':'strict','collector_count':2,'collector_failure_count':0}
    assert evidence_is_trustworthy(settings,data)
    assert not evidence_is_trustworthy(settings,{**data,'age_seconds':121})
    assert not evidence_is_trustworthy(settings,{**data,'collector_failure_count':1})
    assert not evidence_is_trustworthy(settings,{**data,'tls_mode':'unknown'})


def test_transition_and_outbox_rollback_together(settings,monkeypatch):
    # An insertion failure must not record the state as notified.
    original=control.channels
    monkeypatch.setattr(control,'channels',lambda _: {'unknown': object()})
    with pytest.raises(AttributeError):
        control.transition(settings,'collector:pc','FAILED',{'kind':'collector'},1000)
    with control.connect(settings) as db:
        assert db.execute('SELECT count(*) FROM transitions').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM deliveries').fetchone()[0]==0
    monkeypatch.setattr(control,'channels',original)


def test_stale_sending_message_is_superseded_before_delivery(settings):
    control.transition(settings,'collector:pc','FAILED',{'kind':'collector'},1000)
    with control.connect(settings) as db:
        db.execute("UPDATE deliveries SET status='SENDING'")
    control.transition(settings,'collector:pc','CLEAR',{'kind':'collector'},1001)
    # Simulate restart recovery of the original sending record.
    with control.connect(settings) as db:db.execute("UPDATE deliveries SET status='PENDING' WHERE status='SENDING'")
    sender=MagicMock();control.send_due(settings,sender,1002);sender.assert_not_called()
    assert rows(settings)[0]['status']=='SUPERSEDED'


def test_inventory_attempt_backoff_and_last_success_are_preserved(settings):
    import time
    now=time.time()
    control.stamp(settings,last_success_at=now-10,last_inventory_attempt=now)
    store=MagicMock();store.inventory_settings_from_connections.return_value=settings
    inventory=MagicMock()
    control.collect_once(settings,store,lambda _:report(time.time(),False),inventory)
    inventory.assert_not_called()
    assert control.worker_status(settings)['state']['last_success_at']==now-10


def test_worker_diagnostics_require_auth_and_readiness_reports_missing_worker(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import create_app
    settings=Settings(evidence_dir=str(tmp_path),admin_db_path=str(tmp_path/'admin.sqlite3'),monitoring_enabled=True)
    client=TestClient(create_app(settings))
    assert client.get('/api/v1/monitoring/worker/status').status_code in (401,403)
    assert client.get('/api/v1/monitoring/deliveries').status_code in (401,403)
    assert client.post('/api/v1/monitoring/worker/retry-inventory').status_code in (401,403)
    response=client.get('/api/v1/monitoring/worker/ready')
    assert response.status_code==503
    assert response.json()=={'status':'UNHEALTHY'}
