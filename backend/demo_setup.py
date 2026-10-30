"""Prepare a synthetic workspace and PDFs; never approve or apply a document."""
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path

from backend.demo_fixtures import demo_pdfs
from backend.schemas import ApplicantProfile
from backend.storage import Store, WorkspaceConfig


def setup_demo(data_dir: Path, output_dir: Path, workspace_id="scholarship-demo-2026"):
    data_dir, output_dir = data_dir.resolve(), output_dir.resolve()
    intake = data_dir / "intake"
    intake.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    fixtures = demo_pdfs()
    for filename, content in fixtures.items():
        path = output_dir / filename
        if path.exists() and path.read_bytes() != content:
            raise ValueError(f"Refusing to overwrite changed fixture: {path}")
        path.write_bytes(content)
    source = Path(__file__).resolve().parents[1] / "datasets" / "synthetic" / "phase1" / "marks_relaxed_en.json"
    profiles = [ApplicantProfile.model_validate(p | {"workspace_id":workspace_id}) for p in json.loads(source.read_text(encoding="utf-8"))["profiles"]]
    # Known hashes are operator configuration for these generated fixtures only.
    store = Store(data_dir / "niyampulse.sqlite3")
    store.configure(WorkspaceConfig(
        workspace_id=workspace_id, scheme_id="scholarship-demo-2026", issuing_authority="Synthetic Scholarship Board",
        synthetic=True, evaluation_date=date(2026,10,30), profiles=profiles,
        configured_hashes=[hashlib.sha256(data).hexdigest() for data in fixtures.values()],
        intake_directory=str(intake),
    ))
    return store, fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("NIYAMPULSE_DATA_DIR", "var")))
    parser.add_argument("--output-dir", type=Path, default=Path("output/pdf"))
    parser.add_argument("--workspace-id", default="scholarship-demo-2026")
    args = parser.parse_args()
    store, _ = setup_demo(args.data_dir, args.output_dir, args.workspace_id)
    print(f"Configured SYNTHETIC workspace: {args.workspace_id}")
    print(f"Database: {store.path}")
    print(f"PDFs: {args.output_dir.resolve()}")
    print(f"Local corrigendum intake: {store.config(args.workspace_id).intake_directory}")
    print("No notices imported, reviewed, or applied. Review through the API explicitly.")
    print("Decision support only; not official approval.")


if __name__ == "__main__":
    main()
