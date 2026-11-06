"""Assemble allowlisted, portable source modules into one offline Python executable."""
import hashlib
import zipfile
from pathlib import Path

here = Path(__file__).resolve().parent
lab = here.parent
codec = lab / "community_codec"
app = here / "cn-preview.pyz"
sources = {p.relative_to(codec).as_posix(): p.read_bytes() for p in sorted((codec / "cncodec").glob("*.py"))}
sources.update({
    "preview_cli.py": (here / "preview_cli.py").read_bytes(),
    "solar_codec.py": (lab / "solar_study" / "solar_codec.py").read_bytes(),
    "step_delta.py": (lab / "file_study" / "step_delta.py").read_bytes(),
    "step_delta_v2.py": (lab / "file_study" / "step_delta_v2.py").read_bytes(),
    "step_delta_v3.py": (lab / "file_study" / "step_delta_v3.py").read_bytes(),
    "LICENSE": (codec / "LICENSE").read_bytes(),
    "__main__.py": b"from preview_cli import main\nraise SystemExit(main())\n",
})
with zipfile.ZipFile(app, "w") as archive:
    for name, data in sorted(sources.items()):
        entry = zipfile.ZipInfo(name, date_time=(2026, 11, 6, 0, 0, 0))
        entry.external_attr = 0o644 << 16
        archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED)
digest = hashlib.sha256(app.read_bytes()).hexdigest()
(here / "SHA256SUMS").write_text(f"{digest}  {app.name}\n", encoding="ascii")

# The root executable is the entry point documented in the release kit.
(lab / app.name).write_bytes(app.read_bytes())
