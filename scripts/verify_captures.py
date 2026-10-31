"""Verify exact captured source bytes before parser tests; never rewrite evidence."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1] / 'tests/fixtures/official'
    manifest = json.loads((root / 'capture_manifest.json').read_text(encoding='utf-8'))
    failures = []
    for name, record in manifest.items():
        candidates = [root / (name + suffix) for suffix in ('.html', '.txt')]
        path = next((p for p in candidates if p.is_file()), None)
        if path is None or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            failures.append(name)
    if failures:
        raise SystemExit('Capture hash mismatch: ' + ', '.join(failures) +
                         '. Preserve original bytes with .gitattributes; do not regenerate hashes.')
    print(f'{len(manifest)} immutable source capture hashes verified')


if __name__ == '__main__': main()
