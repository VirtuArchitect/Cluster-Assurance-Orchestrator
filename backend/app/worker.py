"""Dedicated unattended collector and sender. Run separately from the API."""
import argparse
from pathlib import Path
import signal
from threading import Event, Thread
import time
from app.core.config import load_settings
from app.services.admin_store import AdminStore
from app.services.inventory_run import run_inventory, write_inventory_evidence
from app.services.monitoring import collect_monitoring
from app.services.monitoring_control import connect, collect_once, send_due, stamp, worker_status
from app.services.process_lock import FileLock


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    settings=load_settings()
    if args.check:
        result=worker_status(settings);print(result['status']);return 0 if result['status']=='RUNNING' else 1
    if not settings.monitoring_enabled:print('Unattended monitoring is disabled');return 1
    lock=FileLock(Path(settings.evidence_dir)/'monitoring-worker.lock')
    if not lock.acquire():print('Another worker owns the appliance volume');return 1
    stop=Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    with connect(settings) as db:
        # A prior crash may have occurred after receiver acceptance. Stable delivery IDs
        # let receivers deduplicate the resulting at-least-once retry.
        db.execute("UPDATE deliveries SET status='PENDING' WHERE status='SENDING'")
    def send_loop():
        while not stop.is_set():
            try:send_due(settings);stamp(settings,sender_error=None)
            except Exception as error:stamp(settings,sender_error=type(error).__name__)
            stop.wait(1)
    sender=Thread(target=send_loop,name='alert-sender',daemon=True);sender.start()
    try:
        store=AdminStore(settings)
        def inventory(effective):
            report=run_inventory(effective)
            write_inventory_evidence(report,effective.evidence_dir)
            if any(c.status != 'HEALTHY' for c in report.collectors): raise RuntimeError('InventoryIncomplete')
        while not stop.is_set():
            started=time.monotonic()
            try:collect_once(settings,store,collect_monitoring,inventory)
            except Exception as error:print('Collection iteration failed:',type(error).__name__,flush=True)
            stop.wait(max(1,settings.monitoring_interval_seconds-(time.monotonic()-started)))
    finally:
        stop.set();sender.join(timeout=12);lock.release()
    return 0

if __name__=='__main__':raise SystemExit(main())
