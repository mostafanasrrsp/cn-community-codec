"""Create a wheel, source archive and portable Python app from a clean source tree."""
import hashlib
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from setuptools import build_meta

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "dist"
FILES = ("README.md", "FORMAT.md", "LICENSE", "pyproject.toml", "setup.cfg",
         "MANIFEST.in", "build_release.py", "setup.py")
SOURCE_GROUPS = ("cncodec/*.py", "tests/test_*.py", "examples/*.csv")


def add_text(archive, name, data):
    entry = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
    entry.external_attr = 0o644 << 16
    archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED)


def build():
    os.environ.setdefault("SOURCE_DATE_EPOCH", "1793923200")
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        for item in FILES:
            shutil.copyfile(ROOT / item, stage / item)
        for pattern in SOURCE_GROUPS:
            for path in ROOT.glob(pattern):
                destination = stage / path.relative_to(ROOT)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
        os.chdir(stage)
        try:
            wheel = build_meta.build_wheel(str(OUT))
            sdist = build_meta.build_sdist(str(OUT))
            app = "cncodec-0.1.0.pyz"
            with zipfile.ZipFile(OUT / app, "w") as archive:
                add_text(archive, "__main__.py", b"from cncodec.__main__ import main\nraise SystemExit(main())\n")
                for source in sorted(Path("cncodec").glob("*.py")):
                    add_text(archive, source.as_posix(), source.read_bytes())
                add_text(archive, "LICENSE", Path("LICENSE").read_bytes())
        finally:
            os.chdir(ROOT)
    with (OUT / "SHA256SUMS").open("w", encoding="ascii") as sums:
        for filename in sorted((wheel, sdist, app)):
            digest = hashlib.sha256((OUT / filename).read_bytes()).hexdigest()
            sums.write(f"{digest}  {filename}\n")


if __name__ == "__main__":
    build()
