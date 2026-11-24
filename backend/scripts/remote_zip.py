"""Read single files from a large remote ZIP with HTTP range requests (no full download).

    python scripts/remote_zip.py list <url>
    python scripts/remote_zip.py get <url> <out_dir> <prefix> [<prefix> ...]
"""
from __future__ import annotations

import io
import sys
import time
import urllib.request
import zipfile
from pathlib import Path


class HttpRangeFile(io.RawIOBase):
    def __init__(self, url: str):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "AGROAI-research/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Length"])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.size, self.pos + n) - 1
        for attempt in range(6):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}",
                                                                "User-Agent": "AGROAI-research/1.0"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                break
            except Exception:
                time.sleep(3 * (attempt + 1))
        else:
            raise IOError("range request failed")
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def main():
    cmd, url = sys.argv[1], sys.argv[2]
    z = zipfile.ZipFile(io.BufferedReader(HttpRangeFile(url), buffer_size=1 << 20))
    if cmd == "list":
        from collections import Counter
        c = Counter("/".join(i.filename.split("/")[:-1]) for i in z.infolist() if not i.is_dir())
        s = Counter()
        for i in z.infolist():
            s["/".join(i.filename.split("/")[:-1])] += i.compress_size
        for k, v in sorted(c.items()):
            print(f"{v:6d} files {s[k] / 1e6:8.0f} MB  {k}")
        return
    out = Path(sys.argv[3])
    # "Pear/fruits/=80" takes a random sample of 80 files from that folder; no "=" takes them all
    import random
    rng = random.Random(5)
    wanted = []
    for spec in sys.argv[4:]:
        prefix, _, k = spec.partition("=")
        files = [i for i in z.infolist() if not i.is_dir() and i.filename.startswith(prefix)
                 and not i.filename.split("/")[-1].startswith("._")]
        rng.shuffle(files)
        wanted += files[:int(k)] if k else files
    n = 0
    for i in wanted:
        dest = out / i.filename
        if dest.exists() and dest.stat().st_size == i.file_size:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(z.read(i))
        n += 1
        if n % 25 == 0:
            print("  got", n, flush=True)
    print("done", n)


if __name__ == "__main__":
    main()
