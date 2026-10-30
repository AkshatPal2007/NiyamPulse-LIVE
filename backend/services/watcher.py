"""Observed local amendment intake with stable-file checks and reconciliation."""
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from backend.legacy_schemas_v1 import WatcherHealth
from backend.services.pdf_intake import MAX_PDF_BYTES
from backend.storage import ServiceError


class _Wake(FileSystemEventHandler):
    def __init__(self, signal):
        self.signal = signal

    def on_any_event(self, event):
        if not event.is_directory:
            self.signal.set()


class LocalAmendmentWatcher:
    """Watch one configured directory for corrigenda; never review or apply them."""
    def __init__(self, service, workspace_id, directory):
        self.service, self.workspace_id = service, workspace_id
        self.directory = Path(directory).resolve()
        self.signal, self.stopping = Event(), Event()
        self.observer = Observer()
        self.worker = Thread(target=self._run, daemon=True, name="niyampulse-local-intake")
        self.last_error = None
        self.last_scan_at = None
        self.pending, self.processed = {}, {}

    def start(self):
        if not self.directory.is_dir():
            self.last_error = "Configured intake directory does not exist"
            return
        try:
            self.observer.schedule(_Wake(self.signal), str(self.directory), recursive=False)
            self.observer.start()
            self.worker.start()
        except OSError:
            self.last_error = "Local directory observer could not start"
            if self.observer.is_alive():
                self.observer.stop()
                self.observer.join(timeout=3)

    def stop(self):
        self.stopping.set()
        self.signal.set()
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=3)
        if self.worker.is_alive():
            self.worker.join(timeout=5)

    def health(self):
        return WatcherHealth(enabled=True, running=self.directory.is_dir() and self.observer.is_alive() and self.worker.is_alive(),
                             watched_directory=str(self.directory), last_error=self.last_error,
                             last_scan_at=self.last_scan_at)

    def _run(self):
        while not self.stopping.is_set():
            self.signal.wait(timeout=0.2)
            self.signal.clear()
            try:
                self._scan()
            except Exception:
                self.last_error = "Local intake scan failed; no amendment was applied"

    def _scan(self):
        self.last_scan_at = datetime.now(timezone.utc)
        if not self.directory.is_dir():
            self.last_error = "Configured intake directory is unavailable"
            return
        for path in self.directory.glob("*"):
            if path.suffix.lower() != ".pdf" or path.resolve().parent != self.directory or not path.is_file():
                continue
            try:
                stat = path.stat()
                signature = (stat.st_size, stat.st_mtime_ns)
                if self.processed.get(path) == signature:
                    continue
                previous = self.pending.get(path)
                if previous is None or previous[0] != signature:
                    self.pending[path] = (signature, time.monotonic())
                    continue
                if time.monotonic() - previous[1] < 0.4:
                    continue
                with path.open("rb") as stream:
                    data = stream.read(MAX_PDF_BYTES + 1)
                after = path.stat()
                if signature != (after.st_size, after.st_mtime_ns):
                    continue
                result = self.service.import_pdf(self.workspace_id, data, filename=path.name,
                                                  kind="CORRIGENDUM", origin_path=path)
                self.service.process(self.workspace_id, result.document.document_id)
                self.processed[path] = signature
                self.pending.pop(path, None)
                self.last_error = None
            except OSError:
                self.last_error = "A PDF is not yet readable; intake will retry"
            except ServiceError as error:
                self.last_error = f"{error.code}: {error}"
                self.processed[path] = signature
