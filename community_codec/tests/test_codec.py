import bz2
import contextlib
import hashlib
import io
import lzma
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
from fractions import Fraction

from cncodec import affine, geometry as gx, standard_charts, transport as tr
from cncodec.__main__ import main


class TransportTest(unittest.TestCase):
    def test_smallest_payload_and_full_size(self):
        for raw in (b"", bytes(range(256)), b"data"*10000, os.urandom(4096)):
            wire = tr.pack_bytes(raw)
            info = tr.metadata(wire)
            self.assertEqual(tr.unpack_bytes(wire), raw)
            self.assertEqual(info["wire_bytes"], 45 + min(map(len, (
                raw, zlib.compress(raw), bz2.compress(raw), lzma.compress(raw, preset=3)))))
            self.assertEqual(info["sha256"], hashlib.sha256(raw).hexdigest())

    def test_verify_all_methods_and_reject_bad_inputs(self):
        raw = b"45679"*8000
        for mode, body in enumerate((
                raw, zlib.compress(raw), bz2.compress(raw), lzma.compress(raw, preset=3))):
            head = tr.HEADER.pack(b"CNF1", mode, len(raw), hashlib.sha256(raw).digest())
            self.assertEqual(tr.unpack_bytes(head + body), raw)
            bad = [head + body[:-1], head + body + b"!", head + body + body,
                   tr.HEADER.pack(b"CNF1", mode, 1000, bytes(32)) + body,
                   bytes([0]) + head[1:] + body, head[:13] + bytes(32) + body]
            for damaged in bad:
                with self.assertRaises(ValueError):
                    tr.unpack_bytes(damaged)

    def test_decompression_and_allocation_limits(self):
        raw = b"0" * 1024**2
        digest = hashlib.sha256(raw).digest()
        for mode, compressed in enumerate((zlib.compress(raw), bz2.compress(raw),
                                            lzma.compress(raw, preset=3)), 1):
            wire = tr.HEADER.pack(b"CNF1", mode, 2048, digest) + compressed
            with self.assertRaises(ValueError):
                tr.unpack_bytes(wire)
        with self.assertRaises(ValueError):
            tr.unpack_bytes(tr.HEADER.pack(b"CNF1", 0, tr.LIMIT + 1, digest))
        with self.assertRaises(ValueError):
            tr.unpack_bytes(tr.HEADER.pack(b"CNF1", 255, 0, digest))

    def test_existing_outputs_preserved_on_error(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()):
            source = Path(directory) / "in"
            destination = Path(directory) / "out"
            source.write_bytes(b"orig")
            destination.write_bytes(b"existing")
            self.assertEqual(main(["pack", str(source), str(destination)]), 1)
            self.assertEqual(main(["unpack", str(source), str(destination), "--force"]), 1)
            self.assertEqual(destination.read_bytes(), b"existing")
            self.assertEqual(main(["pack", str(source), str(source), "--force"]), 1)
            self.assertEqual(source.read_bytes(), b"orig")


class GeometryTest(unittest.TestCase):
    centered = (2.,0.,0.,2.,1.,0.,0.)
    offset = (2.,0.,0.,2.,1.,0.25,-0.5)

    def test_known_records(self):
        # Fixed bytes from the project reference; each should evaluate to 1/2 at (1,0).
        vectors = [
            "2000000080", "200000000200", "0038000000000038",
            "0000003f00000000000000000000003f",
            "0000000000000040000000000000000000000000000000000000000000000040000000000000f03f",
            "0040000000000040003c", "000000400000000000000000000000400000803f",
            "004000000100", "00400000000400", "0000000400000000100001fc00",
            "000000000400000000100001fc00", "00000000100002000000000000",
            "00000000008000800000000000", "000000800080000000",
        ]
        for i, vector in enumerate(vectors):
            wire = gx.HEADER.pack(b"GX01", 2, 1) + bytes([1+2*i]) + bytes.fromhex(vector)
            model, = gx.decode(wire)
            self.assertEqual(affine.response(model, (1,0)), Fraction(1,2))
            self.assertEqual(gx.verify([self.centered], wire)["max_certificate_fraction"], "0")

    def test_offsets_and_flat(self):
        for index, (method, chart) in enumerate(zip(gx.METHODS, gx.CHARTS)):
            raw = self.offset
            if chart is standard_charts:
                payload = chart.encode(method, raw, affine.model(raw), True)
            else:
                payload = chart.encode(method, raw, True)
            wire = gx.HEADER.pack(b"GX01", 2, 1) + bytes([2+2*index]) + payload
            self.assertEqual(gx.decode(wire), [affine.model(raw)])
        flat = (2.,0.,0.,2.,0.,0.,0.)
        rows = [flat, self.offset, self.centered] * 4
        wire = gx.encode(rows)
        self.assertEqual(gx.decode(wire), list(map(affine.model, rows)))
        self.assertEqual(gx.verify(rows, wire)["records"], len(rows))

    def test_scope_confusion_and_bad_payloads(self):
        good = gx.encode([self.centered])
        bad = [b"", b"GZ01"+good[4:], good[:4]+bytes([201])+good[5:], good+b"x",
               good[:-1], good[:9]+b"\xff"+good[10:], good[:9]+b"\x1d",
               gx.HEADER.pack(b"GX01", 2, gx.MAX_RECORDS+1),
               gx.HEADER.pack(b"GX01", 2, 1)+b"\x05"+struct.pack("<eeee",1.,0.,0.,float("nan"))]
        for wire in bad:
            with self.assertRaises(ValueError):
                gx.decode(wire)
        for rows in ([self.offset], [], [self.centered] * 2):
            with self.assertRaises(ValueError):
                gx.verify(rows, good)

    def test_geometry_csv_and_extreme_fallback(self):
        source = b"d,B11,B01,B00,B10,bx,by,id\n1,0x1p+1,0,2,0,0,0,example\n"
        self.assertEqual(list(gx.geometries(source)), [self.centered])
        for invalid in (source.replace(b"0x1p+1", b"nan"), source + b"1\n",
                        source.replace(b",by,", b",bx,")):
            with self.assertRaises(ValueError):
                list(gx.geometries(invalid))
        # No lower-precision layout can represent the dynamic range and direction.
        extreme = (2.0**900,0.,0.,2.0**-900,1.,0.75,-0.25)
        wire = gx.encode([extreme])
        self.assertEqual(wire[9], 10)  # exact offset record
        self.assertEqual(gx.decode(wire), [affine.model(extreme)])
        with self.assertRaises(ValueError):
            gx.encode([(1.,0.,0.,-1.,1.,0.,0.)])


if __name__ == "__main__":
    unittest.main()
