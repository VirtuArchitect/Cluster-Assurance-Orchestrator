"""Durable single-host monitoring control plane. No Prism mutations or shell transport.
SQLite state and the singleton lock live on the shared evidence volume. A separate
sender thread keeps delivery retries independent of slow Prism requests.
"""
from __future__ import annotations
from dataclasses import replace
from contextlib import contextmanager
from datetime import datetime, UTC
from email.message import EmailMessage
from hashlib import sha256
import json
from pathlib import Path
import smtplib
import sqlite3
import ssl
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler

from app.core.config import Settings


@contextmanager
def connect(settings):
    root = Path(settings.evidence_dir)
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / 'monitoring-control.sqlite3', timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS transitions (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS deliveries (
      id TEXT PRIMARY KEY, channel TEXT NOT NULL, payload TEXT NOT NULL,
      status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
      due REAL NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
      last_error TEXT, destination_hash TEXT NOT NULL);
    ''')
    try:
        with db: yield db
    finally: db.close()


def put(db, key, value):
    db.execute('INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
               (key, json.dumps(value)))


def get(db, key, default=None):
    row = db.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
    return json.loads(row['value']) if row else default


def stamp(settings, **values):
    with connect(settings) as db:
        for key, value in values.items(): put(db, key, value)


def fresh_complete(report, max_age=120, now=None):
    now = time.time() if now is None else now
    try:
        parsed = datetime.fromisoformat(report['generated_at'].replace('Z', '+00:00'))
        if parsed.tzinfo is None: return False
        age = now - parsed.timestamp()
        feeds = report.get('collectors', [])
        return (0 <= age <= max_age and report.get('status') == 'COLLECTED'
                and bool(feeds) and all(c.get('complete') is True for c in feeds))
    except (KeyError, ValueError, TypeError): return False


def channels(settings):
    result = {}
    if settings.alert_webhook_url: result['webhook'] = settings.alert_webhook_url
    if settings.alert_email_to and settings.smtp_host and settings.smtp_from:
        result['email'] = '|'.join((settings.smtp_host, str(settings.smtp_port), settings.smtp_from, settings.alert_email_to))
    return result


def transition(settings, key, value, payload, now=None):
    """Atomic state transition + outbox insert. Repeat observations do not re-notify."""
    now = time.time() if now is None else now
    destinations = channels(settings)
    with connect(settings) as db:
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT value FROM transitions WHERE key=?', (key,)).fetchone()
        if previous and previous['value'] == value: return
        # Never emit a recovery notification without having observed the failure.
        if not previous and value == 'CLEAR': return
        if not settings.enable_alerts or not destinations:
            put(db, 'notification_gate', 'Disabled or no complete delivery destination configured')
            return
        for old in db.execute("SELECT id,payload FROM deliveries WHERE status='PENDING'").fetchall():
            if json.loads(old['payload']).get('event_key') == key:
                db.execute("UPDATE deliveries SET status='SUPERSEDED',updated=? WHERE id=?",(now,old['id']))
        db.execute('INSERT INTO transitions(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key,value))
        event = {**payload, 'event_key':key, 'state':value, 'observed_at':datetime.fromtimestamp(now, UTC).isoformat()}
        for channel, destination in destinations.items():
            destination_hash = sha256(destination.encode()).hexdigest()
            # Include transition sequence time: recurring OPEN after CLEAR is a new delivery.
            identity = sha256(f'{key}|{value}|{now}|{channel}'.encode()).hexdigest()
            db.execute('INSERT INTO deliveries(id,channel,payload,status,due,created,updated,destination_hash) VALUES(?,?,?,?,?,?,?,?)',
                       (identity,channel,json.dumps(event),'PENDING',now,now,now,destination_hash))
        put(db, 'notification_gate', 'Enabled; infrastructure events require fresh complete strict-TLS evidence')


def process_report(settings, report, now=None):
    now = time.time() if now is None else now
    feeds = report.get('collectors', [])
    if not feeds:
        transition(settings, 'collector:no-feeds','FAILED',{'kind':'collector','severity':'CRITICAL','summary':'No monitoring feeds returned'},now)
        return
    for source in sorted({str(feed.get('source','unknown')) for feed in feeds}):
        source_feeds = [feed for feed in feeds if str(feed.get('source','unknown')) == source]
        complete = all(feed.get('complete') for feed in source_feeds) and fresh_complete(report,now=now)
        transition(settings, 'collector:'+source, 'CLEAR' if complete else 'FAILED',
                   {'kind':'collector','severity':'WARNING','source':source,
                    'summary':'Source feeds restored' if complete else 'Source feeds incomplete; current source state unknown'}, now)
    trustworthy = fresh_complete(report, now=now) and report.get('tls_mode') == 'strict'
    if fresh_complete(report, now=now): stamp(settings,last_complete_at=now)
    stamp(settings, infrastructure_notifications='READY' if trustworthy else 'GATED: TLS unverified' if fresh_complete(report,now=now) else 'GATED: monitoring evidence stale or incomplete')
    if not trustworthy: return
    for item in report.get('incidents', []):
        if item.get('availability') != 'CURRENT': continue
        microservices = item.get('check_id') == 'A200335' or 'microservices infrastructure' in str(item.get('title', '')).lower()
        # Explicit source resolution alone must not generate an A200335 recovery.
        if microservices and item.get('resolved') is True:
            state = 'RECOVERY_UNVERIFIED'  # independent service validation is not automated here
        elif item.get('resolved') is True: state = 'CLEAR'
        elif item.get('resolved') is False and item.get('severity') in ('CRITICAL','WARNING'): state = item['severity']
        else: continue
        transition(settings,'incident:'+str(item['id']),state,
                   {'kind':'incident','severity':item.get('severity'),'check_id':item.get('check_id'),
                    'source':item.get('source'),'run_id':report.get('run_id'),
                    'summary':'Source observation; verify service impact and incident recovery criteria'},now)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def deliver(settings, channel, identity, payload):
    if channel == 'email':
        message = EmailMessage()
        message['From'] = settings.smtp_from
        message['To'] = settings.alert_email_to
        message['Subject'] = 'Cluster Assurance: '+payload['kind']+' '+payload['state']
        message['Message-ID'] = '<'+identity+'@cluster-assurance.invalid>'
        message.set_content(json.dumps(payload,indent=2))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
            if settings.smtp_username: smtp.login(settings.smtp_username,settings.smtp_password)
            rejected = smtp.send_message(message)
            if rejected: raise RuntimeError('SMTP rejected recipients')
    elif channel == 'webhook':
        target = urlsplit(settings.alert_webhook_url)
        local_test = settings.environment != 'production' and target.hostname in ('127.0.0.1','localhost','::1')
        if target.scheme != 'https' and not (local_test and target.scheme == 'http'):
            raise ValueError('HTTPS required for webhook delivery')
        if target.username or target.password: raise ValueError('Webhook URL userinfo is not allowed')
        request = Request(settings.alert_webhook_url,data=json.dumps(payload).encode(),
                          headers={'Content-Type':'application/json','Idempotency-Key':identity},method='POST')
        opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
        with opener.open(request,timeout=10) as response:
            if not 200 <= response.status < 300: raise RuntimeError('Webhook not accepted')
    else: raise ValueError('Unknown channel')


def send_due(settings, sender=deliver, now=None):
    now = time.time() if now is None else now
    stamp(settings, sender_heartbeat=now)
    if not settings.enable_alerts: return
    with connect(settings) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM deliveries WHERE status='PENDING' AND due<=? ORDER BY created LIMIT 1",(now,)).fetchone()
        if not row: return
        db.execute("UPDATE deliveries SET status='SENDING',updated=? WHERE id=?",(now,row['id']))
    payload = json.loads(row['payload'])
    with connect(settings) as db:
        current = db.execute('SELECT value FROM transitions WHERE key=?',(payload['event_key'],)).fetchone()
        if current and current['value'] != payload['state']:
            db.execute("UPDATE deliveries SET status='SUPERSEDED',updated=? WHERE id=?",(now,row['id']))
            return
    if payload.get('kind') == 'incident':
        from app.services.monitoring import latest_monitoring
        try:
            latest = latest_monitoring(settings.evidence_dir)
            trusted = latest.get('tls_mode') == 'strict' and fresh_complete(latest, now=now)
        except Exception: trusted = False
        if not trusted:
            with connect(settings) as db:
                db.execute("UPDATE deliveries SET status='PENDING',due=?,last_error='EvidenceGate' WHERE id=?",(now+30,row['id']))
            return
    destination = channels(settings).get(row['channel'])
    if not destination or sha256(destination.encode()).hexdigest() != row['destination_hash']:
        failure = 'DestinationChanged: review queued message before reconfiguration'
    else:
        try:
            sender(settings,row['channel'],row['id'],json.loads(row['payload']))
            with connect(settings) as db:
                db.execute("UPDATE deliveries SET status='DELIVERED',attempts=attempts+1,updated=?,last_error=NULL WHERE id=?",(now,row['id']))
            return
        except Exception as error: failure = type(error).__name__  # never retain URL/credentials/error text
    attempts = row['attempts']+1
    state = 'DEAD' if attempts >= settings.alert_max_attempts or failure.startswith('DestinationChanged') else 'PENDING'
    with connect(settings) as db:
        db.execute('UPDATE deliveries SET status=?,attempts=?,due=?,updated=?,last_error=? WHERE id=?',
                   (state,attempts,now+min(3600,15*2**min(attempts-1,8)),now,failure,row['id']))


def worker_status(settings, now=None):
    now = time.time() if now is None else now
    with connect(settings) as db:
        states = {row['key']:json.loads(row['value']) for row in db.execute('SELECT * FROM state')}
        counts = {row['status']:row['n'] for row in db.execute('SELECT status,count(*) n FROM deliveries GROUP BY status')}
        heartbeat = states.get('collector_heartbeat')
        sender = states.get('sender_heartbeat')
        stale = not heartbeat or now-heartbeat > settings.monitoring_stale_seconds
        sender_stale = not sender or now-sender > settings.monitoring_stale_seconds
        status = 'DISABLED' if not settings.monitoring_enabled else 'UNHEALTHY' if stale or sender_stale else 'DEGRADED' if states.get('last_error') or states.get('inventory_error') or states.get('sender_error') or counts.get('DEAD',0) else 'RUNNING'
        oldest = db.execute("SELECT min(created) n FROM deliveries WHERE status IN ('PENDING','SENDING')").fetchone()['n']
    if status == 'RUNNING' and oldest is not None and now-oldest > settings.monitoring_stale_seconds: status='DEGRADED'
    return {'status':status,'enabled':settings.monitoring_enabled,'collector_age_seconds':None if not heartbeat else max(0,now-heartbeat),
            'sender_age_seconds':None if not sender else max(0,now-sender),'queue':counts,
            'oldest_pending_age_seconds':None if oldest is None else max(0,now-oldest),
            'state':{**states,'notifications_enabled':settings.enable_alerts,'configured_channels':list(channels(settings))},'scope':'Single-host durable worker; receiver acceptance is not human acknowledgement'}


def collect_once(settings, store, collect, inventory, now=None):
    now = time.time() if now is None else now
    stamp(settings, collector_heartbeat=now, last_attempt_at=now)
    # Force the safety boundary even if saved configuration changes later.
    try:
        effective = replace(store.inventory_settings_from_connections(),read_only_mode=True,enable_ncc=False,enable_ssh=False)
        if effective.demo_mode: raise ValueError('Unattended worker requires live read-only mode')
        report = collect(effective)
        process_report(settings,report)
        failed = not fresh_complete(report)
        stamp(settings,last_error='IncompleteFeeds' if failed else None,last_run_id=report.get('run_id'),collector_heartbeat=time.time())
        if not failed: stamp(settings,last_success_at=time.time())
        transition(settings,'worker:collection','CLEAR',{'kind':'collector','severity':'WARNING','summary':'Collection loop restored'})
        with connect(settings) as db: last_inventory = get(db,'last_inventory_attempt',0)
        if time.time()-last_inventory >= settings.inventory_interval_seconds:
            try:
                stamp(settings,last_inventory_attempt=time.time())
                inventory(effective)
                stamp(settings,last_inventory_at=time.time(),inventory_error=None)
                transition(settings,'worker:inventory','CLEAR',{'kind':'collector','severity':'WARNING','summary':'Inventory collection restored'})
            except Exception as error:
                stamp(settings,inventory_error=type(error).__name__)
                transition(settings,'worker:inventory','FAILED',{'kind':'collector','severity':'WARNING','summary':'Inventory collection failed; retained entries may be stale'})
        return report
    except Exception as error:
        stamp(settings,last_error=type(error).__name__,collector_heartbeat=time.time())
        transition(settings,'worker:collection','FAILED',{'kind':'collector','severity':'CRITICAL','summary':'Collection loop failed; current estate status unknown'})
        raise
