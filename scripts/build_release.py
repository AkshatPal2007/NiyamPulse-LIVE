"""Build the existing UI with its npm lockfile; no deployment or data access."""
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    npm = shutil.which('npm')
    if not npm: raise SystemExit('Node.js/npm is required for the frontend build')
    for args in [['ci', '--include=dev'], ['run', 'build']]:
        subprocess.run([npm, '--prefix', str(root / 'frontend'), *args], cwd=root, check=True)
    print('Frontend release build complete; no service was deployed')


if __name__ == '__main__': main()
