"""Workspace test directories with inherited Windows ACLs (no mode-0700 mkdir)."""
from pathlib import Path
import shutil
import uuid


class LocalTemporaryDirectory:
    def __init__(self):
        self.base = (Path(__file__).resolve().parents[2] / "tmp" / "tests").resolve()
        self.path = self.base / f"test-{uuid.uuid4().hex}"
        self.path.mkdir(parents=True)
        self.name = str(self.path)

    def cleanup(self):
        target = self.path.resolve()
        if not target.is_relative_to(self.base) or target == self.base:
            raise ValueError("Test cleanup target is outside the workspace test directory")
        shutil.rmtree(target)
