"""Native standalone source monitor; runs without the browser or frontend."""
import argparse
import os
from pathlib import Path
from threading import Event

from backend.exam_store import ExamStore
from backend.services.source_monitor import SourceMonitor,SourceScheduler


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,default=Path(os.environ.get("NIYAMPULSE_DATA_DIR","var/production")))
    parser.add_argument("--check",help="Check one configured source ID, then exit")
    parser.add_argument("--discover",action="store_true",help="Persist detected notices; otherwise use dry-run")
    parser.add_argument("--enable",action="store_true",help="Enable only after a successful real mapped source check")
    args=parser.parse_args()
    if args.enable and (not args.check or not args.discover):
        parser.error("--enable requires --check SOURCE_ID and --discover")
    if args.check:
        monitor=SourceMonitor(ExamStore(args.data_dir/"niyampulse.sqlite3"))
        result=monitor.check(args.check,dry_run=not args.discover,enable=args.enable)
        print(result.model_dump_json(indent=2))
        if result.errors: raise SystemExit(1)
        return
    from backend.services.auth import AuthSettings
    from backend.operations import production_runtime
    settings=AuthSettings.from_env()
    if settings.production:
        if not args.data_dir.is_absolute():parser.error('Production requires an absolute --data-dir')
        os.environ['NIYAMPULSE_DATA_DIR']=str(args.data_dir)
    with production_runtime(settings):
        monitor=SourceMonitor(ExamStore(args.data_dir/'niyampulse.sqlite3'))
        from backend.services.processing import ProcessingService,ProcessingScheduler
        from backend.services.sarvam import SarvamService
        from backend.services.vision import VisionService
        ai=SarvamService(monitor.store)
        processing=ProcessingScheduler(ProcessingService(ai,VisionService(ai)));processing.start()
        scheduler=SourceScheduler(monitor);scheduler.start()
        print("NiyamPulse official-source worker running; only individually enabled, tested sources are polled.")
        try:
            while scheduler.thread.is_alive(): Event().wait(1)
        except KeyboardInterrupt: pass
        finally:
            processing.stop();scheduler.stop()


if __name__=="__main__": main()
