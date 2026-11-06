"""Eight complete per-file controls, with the same settings as the v1 AP242 study."""
import bz2
import gzip
import io
import lzma
import subprocess
import zipfile


def command(argv, data=None):
    return subprocess.run(argv, input=data, stdout=subprocess.PIPE, check=True).stdout


def native_archive(data, name, level):
    out = io.BytesIO()
    entry = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=level)
    return out.getvalue()


def unzip(data, name):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.namelist() != [name]:
            raise ValueError("Unexpected STPZ structure")
        return archive.read(name)


def methods(name):
    return {
        "stpz-deflate6": (lambda d: native_archive(d, name, 6), lambda d: unzip(d, name)),
        "stpz-deflate9": (lambda d: native_archive(d, name, 9), lambda d: unzip(d, name)),
        "gzip9": (lambda d: gzip.compress(d, compresslevel=9, mtime=0), gzip.decompress),
        "bzip2-9": (bz2.compress, bz2.decompress),
        "zstd19": (lambda d: command(["zstd", "-q", "--single-thread", "-19", "-c"], d),
                   lambda d: command(["zstd", "-dq", "-c"], d)),
        "brotli11": (lambda d: command(["brotli", "-q", "11", "-c"], d),
                     lambda d: command(["brotli", "-dc"], d)),
        "xz6": (lambda d: lzma.compress(d, preset=6), lzma.decompress),
        "xz9": (lambda d: lzma.compress(d, preset=9), lzma.decompress),
    }
