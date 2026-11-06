"""Exercise the shipping reader, including historical frames, malformed indexes and expansion limits."""
import hashlib
import lzma
import shutil
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "cn-preview.pyz"
sys.path.insert(0, str(APP))
try:
    import preview_cli
    import step_delta_v3 as codec
finally:
    sys.path.pop(0)

PREFIX = b"ISO-10303-21;"
MARKER = bytes([codec.v2.DECIMAL])


def dictionary(text, entries, indexes, literals=b""):
    widths = codec.DICT_WIDTHS.pack(len(text), 0, 0, len(entries), len(indexes))
    return widths + text + entries + indexes + literals


class SXD3(unittest.TestCase):
    def test_lexical_fidelity(self):
        many_entries = b" ".join(str(i).encode() + b".405" for i in range(300))
        samples = [
            PREFIX,
            PREFIX + b"\r\n#8 = FACET('2.4',#7,0.1200,-0.0,+2.410E-10);/*0.1200*/\n",
            PREFIX + b" '1.' '.1' '1.002' '-01.002' '1.002' 2.3300E+001 2.3300E+001",
            PREFIX + b"\0\r\n#0=STUFF(#999999999,'A''B',3.0E+121,#0);\r\n",
            PREFIX + (b"\n#4 =(3." + b"0" * 350 + b"2);\n") * 5,
            PREFIX + (many_entries + b" ") * 3,
        ]
        for method in codec.METHODS:
            if method.endswith("brotli") and not shutil.which("brotli"):
                continue
            for raw in samples:
                with self.subTest(method=method, size=len(raw)):
                    frame = codec.pack(raw, method)
                    self.assertEqual(codec.profile_name(frame), method)
                    self.assertEqual(codec.unpack(frame), raw)

    def test_rejects_malformed_dictionaries(self):
        cases = {
            "duplicate entry": dictionary(MARKER*4, b"1.0\0"*2, b"\1\1\2\2"),
            "invalid entry": dictionary(MARKER*2, b"x\0", b"\1\1"),
            "single-use entry": dictionary(MARKER, b"1.0\0", b"\1"),
            "truncated index": dictionary(MARKER, b"", b"\x81"),
            "noncanonical index": dictionary(MARKER, b"", b"\x81\x00"),
            "unknown index": dictionary(MARKER, b"", b"\x01"),
            "oversized index": dictionary(MARKER, b"", b"\x81\x80"),
            "invalid literal": dictionary(MARKER, b"", b"\0", b"1.x\0"),
            "known literal": dictionary(MARKER*3, b"1.0\0", b"\1\1\0", b"1.0\0"),
            "trailing literal data": dictionary(MARKER, b"", b"\0", b"1.0\0unused"),
            "unterminated literal": dictionary(MARKER, b"", b"\0", b"1.0"),
            "trailing index": dictionary(MARKER, b"", b"\0\0", b"1.0\0"),
            "bad width": codec.DICT_WIDTHS.pack(0xffffffff, 0, 0, 0, 0),
            "short widths": b"\x01"*19,
            "long entry": dictionary(MARKER*2, b"1."+b"9"*128+b"\0", b"\1\1"),
        }
        for label, payload in cases.items():
            with self.subTest(case=label), self.assertRaises(ValueError):
                codec.restore_dictionary(payload, 65536)

    def test_frame_boundaries(self):
        raw = PREFIX + b" (1.00,1.00);"
        for method in codec.METHODS:
            if method.endswith("brotli") and not shutil.which("brotli"):
                continue
            frame = codec.pack(raw, method)
            wrong_digest = frame[:8] + bytes([frame[8] ^ 128]) + frame[9:]
            cases = [frame[:-1], frame+b"x", wrong_digest, b"NOPE"+frame[4:],
                     frame[:40]+b"\xff"+frame[41:],
                     frame[:4]+struct.pack("<I", codec.v2.LIMIT+1)+frame[8:],
                     frame[:4]+struct.pack("<I", 14)+frame[8:]]
            for index, bad in enumerate(cases):
                with self.subTest(method=method, corruption=index), self.assertRaises((ValueError, lzma.LZMAError)):
                    codec.unpack(bad)
        digest = hashlib.sha256(PREFIX).digest()
        header = codec.HEADER.pack(codec.MAGIC, len(PREFIX), digest, 1)
        with self.assertRaises(ValueError):
            codec.unpack(header + lzma.compress(b"A"*10000))
        for profile in (2, 3):
            header = codec.HEADER.pack(codec.MAGIC, len(PREFIX), digest, profile)
            with patch.object(codec.solar_codec, "brotli", side_effect=AssertionError("child started")):
                with self.assertRaisesRegex(ValueError, "large-window"):
                    codec.unpack(header + b"\x11")

    def test_selector_keeps_prior_modes_and_portable_fallback(self):
        raw = PREFIX + (b"\n#9=POINT('',(1.000,1.000,-0.250,-0.250));" * 16)
        expected = {"CNF1", "SXD1", "SXD2-split-tuned", "SXD2-dual-floats-tuned", "SXD3-dictionary-xz"}
        compact = expected | {"SXD2-split-brotli", "SXD3-dual-floats-brotli", "SXD3-dictionary-brotli"}
        frame, sizes, _ = preview_cli.select(raw)
        self.assertEqual(set(sizes), expected)
        self.assertEqual(len(frame), min(sizes.values()))
        if shutil.which("brotli"):
            frame, sizes, _ = preview_cli.select(raw, with_brotli=True)
            self.assertEqual(set(sizes), compact)
            self.assertEqual(len(frame), min(sizes.values()))
        with patch.object(shutil, "which", return_value=None):
            frame, sizes, notes = preview_cli.select(raw, with_brotli=True)
            self.assertEqual(set(sizes), expected)
            self.assertEqual(len(notes), 1)
            self.assertEqual(preview_cli.restore(frame), raw)

    def test_frozen_v2(self):
        # Created with the released 0.2 executable, SHA-256 1b0abbaf…618ef1e3,
        # using synthetic STEP bytes shared by the three archived methods.
        fixtures = Path(__file__).with_name("v2-frames")
        raw = (fixtures / "step.orig").read_bytes()
        frames = sorted(fixtures.glob("*.cn"))
        self.assertEqual({f.stem for f in frames}, set(codec.v2.PROFILES))
        for f in frames:
            if f.stem.endswith("brotli") and not shutil.which("brotli"):
                continue
            with self.subTest(method=f.stem):
                self.assertEqual(preview_cli.restore(f.read_bytes()), raw)


if __name__ == "__main__":
    unittest.main()
