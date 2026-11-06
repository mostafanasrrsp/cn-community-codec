"""Post-hoc scientific-container controls for the six frozen SURFRAD source files."""
import argparse
import base64
import hashlib
import io
import json
import platform
import subprocess
import zlib
from pathlib import Path
import zipfile

import blosc2
import h5py
import imagecodecs
from imagecodecs.numcodecs import Brotli
import numcodecs
import zarr
import numpy as np

ROOT = Path(__file__).resolve().parent


def verify(raw, restored, saved_digest):
    if restored != raw or hashlib.sha256(restored).digest() != saved_digest:
        raise ValueError("Decoded bytes or persisted source SHA-256 differ")


def hdf_case(raw, prefix, body, width, rows_per_chunk, shuffle):
    """Measure a complete HDF5 file; inspect the first chunk independently of HDF5 readback."""
    buffer = io.BytesIO()
    with h5py.File(buffer, "w", libver="latest") as store:
        store.attrs["source_prefix"] = np.void(prefix)
        store.attrs["source_sha256"] = np.void(hashlib.sha256(raw).digest())
        records = store.create_dataset("records", data=np.frombuffer(body, dtype=f"V{width}"),
                                       chunks=(rows_per_chunk,), shuffle=shuffle,
                                       compression="gzip", compression_opts=9, track_times=False)
        if len(body) < rows_per_chunk * width:
            raise ValueError("Validation expects a complete first chunk")
        records.flush()
        mask, compressed = records.id.read_direct_chunk((0,))
        chunk = body[:rows_per_chunk * width]
        expected = b"".join(chunk[column::width] for column in range(width)) if shuffle else chunk
        if mask or zlib.decompress(compressed) != expected:
            raise ValueError("Raw HDF5 chunk did not match the specified shuffle and DEFLATE")
    frame = buffer.getvalue()
    with h5py.File(io.BytesIO(frame), "r") as store:
        restored = bytes(store.attrs["source_prefix"]) + store["records"][:].tobytes()
        verify(raw, restored, bytes(store.attrs["source_sha256"]))
    return len(frame)


def blosc_case(raw, prefix, body, width, rows_per_chunk, blocksize, filter_name):
    """Construct a portable full frame and restore from the frame alone."""
    filter_id = {
        "none": blosc2.Filter.NOFILTER,
        "shuffle": blosc2.Filter.SHUFFLE,
        "bitshuffle": blosc2.Filter.BITSHUFFLE,
    }[filter_name]
    filters = [blosc2.Filter.NOFILTER] * 5 + [filter_id]
    params = blosc2.CParams(codec=blosc2.Codec.ZSTD, clevel=9, typesize=width, nthreads=1,
                           blocksize=blocksize, filters=filters)
    size = width * rows_per_chunk
    stage = blosc2.SChunk(chunksize=size, cparams=params, contiguous=True,
                          meta={"source_prefix": prefix, "source_sha256": hashlib.sha256(raw).digest()})
    for start in range(0, len(body), size):
        stage.append_data(body[start:start + size])
    frame = stage.to_cframe()
    source = blosc2.schunk_from_cframe(frame, copy=True)
    if source.typesize != width or source.cparams.filters != filters:
        raise ValueError("Unexpected element width or filter in serialized Blosc2 frame")
    restored = source.meta["source_prefix"] + b"".join(source.decompress_chunk(i) for i in range(source.nchunks))
    verify(raw, restored, source.meta["source_sha256"])
    return len(frame)


def zarr_case(raw, prefix, body, width, height, compressor, delta, deflate_zip):
    """Pack one existing Zarr v2 array and its metadata into an ordinary ZipStore."""
    buffer = io.BytesIO()
    filters = [numcodecs.Shuffle(width)]
    if delta:
        filters.append(numcodecs.Delta(dtype="u1"))
    attrs = {"source_prefix": base64.b64encode(prefix).decode(), "source_sha256": hashlib.sha256(raw).hexdigest()}
    zip_mode = zipfile.ZIP_DEFLATED if deflate_zip else zipfile.ZIP_STORED
    with zarr.storage.ZipStore(buffer, mode="w", compression=zip_mode) as store:
        zarr.create_array(store=store, data=np.frombuffer(body, dtype=f"S{width}"), chunks=(height,),
                          filters=filters, compressors=compressor, zarr_format=2, attributes=attrs)
    frame = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(frame)) as archive:
        packed_chunk_bytes = archive.getinfo("0").compress_size
        shuffled = compressor.decode(archive.read("0"))
        if delta:
            shuffled = filters[-1].decode(shuffled)
        if bytes(shuffled) != b"".join(body[i::width] for i in range(width)):
            raise ValueError("Zarr's decoded payload did not contain the exact byte shuffle")
    with zarr.storage.ZipStore(io.BytesIO(frame), mode="r") as store:
        array = zarr.open_array(store, mode="r")
        restored = base64.b64decode(array.attrs["source_prefix"]) + array[:].tobytes()
        verify(raw, restored, bytes.fromhex(array.attrs["source_sha256"]))
    return len(frame), packed_chunk_bytes


def compare(raw):
    lines = raw.splitlines(keepends=True)
    prefix = b"".join(lines[:2])
    data_rows = lines[2:]
    width, height = len(data_rows[0]), len(data_rows)
    if width != 240 or height != 1440 or any(len(row) != width for row in data_rows):
        raise ValueError("Unexpected NOAA record shape")
    body = raw[len(prefix):]
    sizes = {}
    for n in (120, 360, height):
        for shuffle in (False, True):
            label = "shuffle" if shuffle else "unfiltered"
            sizes[f"HDF5-gzip9-{label}-rows{n}"] = hdf_case(raw, prefix, body, width, n, shuffle)
    for n in (120, 360, height):
        for block in (0, width * n):
            for filter_name in ("none", "shuffle", "bitshuffle"):
                sizes[f"Blosc2-zstd9-{filter_name}-rows{n}-blk{block}"] = blosc_case(
                    raw, prefix, body, width, n, block, filter_name)
    zarr_chunks = {}
    for codec_name, compressor in (("brotli11", Brotli(level=11)), ("lzma6", numcodecs.LZMA(preset=6)),
                                   ("zstd22", numcodecs.Zstd(level=22))):
        for delta in (False, True):
            for deflate_zip in (False, True):
                filt = "shuffle-delta8" if delta else "shuffle"
                outer = "deflate" if deflate_zip else "stored"
                setting = f"Zarr2-{codec_name}-{filt}-zip{outer}"
                sizes[setting], zarr_chunks[setting] = zarr_case(
                    raw, prefix, body, width, height, compressor, delta, deflate_zip)
    return sizes, zarr_chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("--output", type=Path, default=Path("local-container-controls.json"))
    args = parser.parse_args()
    numcodecs.register_codec(Brotli)
    prior = json.loads((ROOT / "sensitivity-results.json").read_text())
    files = []
    for item in prior["files"]:
        raw = (args.cache / item["file"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("Input digest differs: " + item["file"])
        sizes, zarr_chunks = compare(raw)
        # Existing XZ frame, direct source, with the row width provided to its native delta filter.
        xz_frame = subprocess.run(["xz", "--threads=1", "-c", "--delta=dist=240", "--lzma2=preset=9e"],
                                  input=raw, stdout=subprocess.PIPE, check=True).stdout
        xz_restored = subprocess.run(["xz", "-dc"], input=xz_frame, stdout=subprocess.PIPE, check=True).stdout
        verify(raw, xz_restored, bytes.fromhex(item["sha256"]))
        best = min(sizes, key=sizes.get)
        files.append({"file": item["file"], "sha256": item["sha256"], "sizes": sizes,
                      "zarr_encoded_chunk_bytes": zarr_chunks,
                      "posthoc_oracle_setting": best, "posthoc_oracle_bytes": sizes[best],
                      "xz_native_stride240_bytes": len(xz_frame),
                      "direct_eight_oracle_bytes": item["eight_arm_best_bytes"], "srt2_bytes": item["srt2_brotli"]})
    totals = {setting: sum(f["sizes"][setting] for f in files) for setting in files[0]["sizes"]}
    fixed_best = min(totals, key=totals.get)
    oracle_total = sum(f["posthoc_oracle_bytes"] for f in files)
    srt2_total = sum(f["srt2_bytes"] for f in files)
    versions = {"python": platform.python_version(), "hdf5": h5py.version.hdf5_version,
                "h5py": h5py.__version__, "numpy": np.__version__, "blosc2_python": blosc2.__version__,
                "c_blosc2": blosc2.VERSION_STRING, "blosc_zstd": blosc2.clib_info(blosc2.Codec.ZSTD)[1].decode(),
                "zarr": zarr.__version__, "numcodecs": numcodecs.__version__, "imagecodecs": imagecodecs.__version__,
                "imagecodecs_brotli": imagecodecs.brotli_version(),
                "xz": subprocess.check_output(["xz", "--version"], text=True).strip()}
    matched = "Zarr2-brotli11-shuffle-zipdeflate"
    zarr_payload = sum(item["zarr_encoded_chunk_bytes"][matched] for item in files)
    output = {"best_zarr_archive_breakdown": {"setting": matched, "encoded_body_chunks": zarr_payload,
                                               "metadata_and_zip_framing": totals[matched] - zarr_payload},
              "scope": "Post-hoc container sensitivity on exact six held-out files; complete frames with source prefix and SHA-256.",
              "versions": versions, "files": files, "fixed_setting_totals": totals,
              "best_fixed_setting": fixed_best, "best_fixed_bytes": totals[fixed_best],
              "per_file_oracle_bytes": oracle_total, "srt2_brotli_bytes": srt2_total,
              "srt2_fraction_below_per_file_oracle": 1 - srt2_total / oracle_total,
              "verified_round_trips": len(totals) * len(files),
              "xz_native_stride240_bytes": sum(f["xz_native_stride240_bytes"] for f in files),
              "xz_native_stride240_verified_round_trips": len(files)}
    args.output.write_text(json.dumps(output, indent=2) + "\n")


if __name__ == "__main__":
    main()
