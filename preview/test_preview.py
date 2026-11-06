"""End-to-end offline safety and profile selection tests against the shipped executable."""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().with_name("cn-preview.pyz")
if not APP.exists():
    APP = APP.parent.parent / "cn-preview.pyz"


def solar(day=b" Fort Peck", count=720):
    header = day + b"\n   48.31 -105.10  634 m version 1\n"
    rows = []
    for i in range(count):
        time = f"2020  32  2  1 {i // 60:2} {i % 60:2}  0.000 91.14 "
        fields = [f"{(i * (j + 1) + i*i % 123) % 100:6.1f} 0 " for j in range(20)]
        row = (time + "".join(fields)).encode().ljust(239) + b"\n"
        rows.append(row)
    return header + b"".join(rows)


def step():
    return (b"ISO-10303-21;\nDATA;\n" + b"".join(
        f"#{i}=ITEM(#{i-2}, #{i-1});\n".encode() for i in range(3, 2000))
        + b"ENDSEC;\nEND-ISO-10303-21;\n")


class Preview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.env = dict(os.environ, PATH="")

    def command(self, *args, ok=True):
        p = subprocess.run([sys.executable, "-I", str(APP), *args], cwd=self.dir, env=self.env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(p.returncode == 0, ok, (args, p.stderr, p.stdout))
        if ok and p.stdout:
            return json.loads(p.stdout)
        self.assertNotIn("Traceback", p.stderr)
        return p.stderr

    def pack(self, raw, *opts):
        (self.dir / "in").write_bytes(raw)
        summary = self.command("pack", "in", "wire", "--force", *opts)
        self.assertEqual(summary["wire_bytes"], (self.dir / "wire").stat().st_size)
        self.assertEqual(summary["wire_bytes"], min(summary["candidate_bytes"].values()))
        self.assertEqual(self.command("inspect", "wire")["sha256"], hashlib.sha256(raw).hexdigest())
        self.command("unpack", "wire", "out", "--force")
        self.assertEqual((self.dir / "out").read_bytes(), raw)
        return summary

    def test_profiles_and_offline_optional_fallback(self):
        self.assertEqual(self.pack(b"")["format"], "CNF1")
        info = self.pack(step())
        self.assertIn("SXD1", info["candidate_bytes"])
        self.assertIn("SXD2-dual-floats-tuned", info["candidate_bytes"])
        self.assertEqual(info["format"], "SXD1")
        self.assertNotIn("SXD1", self.pack(step()+b"\x1f")["candidate_bytes"])
        info = self.pack(solar(), "--with-brotli")
        self.assertEqual(info["format"], "SRT2")
        self.assertIn("Brotli CLI unavailable", info["notes"][0])
        for raw in [solar(b"Unrelated Station"), solar()[:-1], solar().replace(b"91.14", b"xx.xx")]:
            self.assertEqual(set(self.pack(raw)["candidate_bytes"]), {"CNF1"})

    def test_step_small_refs_after_long_declaration(self):
        # A one-digit reference can need a five-byte delta against a large declaration.
        raw = b"ISO-10303-21;\n#999999999=ITEM(" + b"#0," * 1000 + b"#0);"
        sys.path.insert(0, str(APP))
        try:
            import step_delta
            (self.dir / "wire").write_bytes(step_delta.pack(raw))
        finally:
            sys.path.pop(0)
        self.command("unpack", "wire", "out")
        self.assertEqual((self.dir / "out").read_bytes(), raw)

    def test_invalid_frames_and_untouched_output(self):
        for raw in [b"small", step(), solar()]:
            self.pack(raw)
            original_wire = (self.dir / "wire").read_bytes()
            tag = original_wire[:4]
            length_at, huge, digest_at = {
                b"CNF1": (5, struct.pack("<Q", 2**32), 13),
                b"SXD1": (4, struct.pack("<I", 2**26), 8),
                b"SXD2": (4, struct.pack("<I", 2**26), 8),
                b"SRT2": (9, struct.pack(">I", 2**32 - 1), 13),
            }[tag]
            wrong_size = bytearray(original_wire)
            wrong_size[length_at:length_at + len(huge)] = huge
            wrong_hash = bytearray(original_wire)
            wrong_hash[digest_at] ^= 1
            for bad in (original_wire[:-1], original_wire + b"x", wrong_size, wrong_hash):
                (self.dir / "wire").write_bytes(bad)
                self.command("unpack", "wire", "out", "--force", ok=False)
                self.assertEqual((self.dir / "out").read_bytes(), raw)
        self.command("pack", "in", "in", "--force", ok=False)
        self.command("pack", "in", "out", ok=False)

    def test_frozen_v1_frames(self):
        fixtures = Path(__file__).with_name("v1-frames")
        for source in sorted(fixtures.glob("*.cn")):
            with self.subTest(source=source.name):
                if source.stem.endswith("brotli"):
                    self.command("unpack", str(source), "out", "--force", ok=False)
                    if not shutil.which("brotli"):
                        continue
                    self.env["PATH"] = os.environ["PATH"]
                self.command("unpack", str(source), "out", "--force")
                self.assertEqual((self.dir / "out").read_bytes(), source.with_suffix(".orig").read_bytes())

    def test_sxd2_profiles(self):
        sys.path.insert(0, str(APP))
        try:
            import step_delta_v2 as codec
        finally:
            sys.path.pop(0)
        raw = (b"ISO-10303-21;\r\n#123  =ENTITY(#+0001,#002,-1.234E+04,#6,0.000);"
               b"/* '#123' */\r\n#999999999=I(#0,#0);")
        for profile in codec.PROFILES:
            if profile == "split-brotli" and not shutil.which("brotli"):
                continue
            with self.subTest(profile=profile):
                frame = codec.pack(raw, profile)
                wire = self.dir / "wire"
                wire.write_bytes(frame)
                if profile == "split-brotli":
                    self.command("unpack", "wire", "out", "--force", ok=False)
                    self.env["PATH"] = os.environ["PATH"]
                self.assertEqual(self.command("inspect", "wire")["method"], profile)
                self.command("unpack", "wire", "out", "--force")
                self.assertEqual((self.dir / "out").read_bytes(), raw)
                for bad in (frame[:-1], frame+b"extra", frame[:40]+b"\xff"+frame[41:]):
                    wire.write_bytes(bad)
                    self.command("unpack", "wire", "out", "--force", ok=False)
                    self.assertEqual((self.dir / "out").read_bytes(), raw)

    def test_geometry_stays_explicit(self):
        (self.dir / "geo").write_text("B00,B01,B10,B11,d,bx,by\n2,0,0,2,1,0,0\n")
        self.command("geometry-pack", "geo", "gx")
        self.command("geometry-verify", "geo", "gx")
        self.assertEqual(self.command("geometry-query", "gx", "0", "0.5", "0")["transmission"], 0.75)
        self.command("unpack", "gx", "no-file", ok=False)
        self.assertFalse((self.dir / "no-file").exists())
        self.assertEqual(self.pack((self.dir / "gx").read_bytes())["format"], "CNF1")


if __name__ == "__main__":
    unittest.main()
