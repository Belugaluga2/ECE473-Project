"""Bounded, read-only HTTP range access for large public research ZIP archives."""
from __future__ import annotations

import io
import re

import requests


class HTTPRangeFile(io.RawIOBase):
    """Seekable file that refuses servers which ignore Range or return wrong bytes.

    This permits zipfile to fetch a few small members of a multi-GB archive.
    No request may read more than max_read bytes; there is no full-download fallback.
    """

    def __init__(self, url, session=None, max_read=32 * 1024 * 1024):
        super().__init__()
        self.url = url
        self.session = session or requests.Session()
        self.max_read = max_read
        self.pos = 0
        self.bytes_received = 0
        self.size = None
        self._request(0, 0)

    def _request(self, start, end):
        with self.session.get(self.url, headers={"Range": f"bytes={start}-{end}",
                                                 "Accept-Encoding": "identity"},
                              stream=True, timeout=45) as response:
            if response.status_code != 206:
                raise OSError(f"Expected HTTP 206 for a bounded range, got {response.status_code}")
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
            if not match or tuple(map(int, match.groups()[:2])) != (start, end):
                raise OSError("Server returned an unexpected Content-Range")
            size = int(match.group(3))
            if self.size is not None and size != self.size:
                raise OSError("Archive size changed between requests")
            self.size = size
            body = response.raw.read(end - start + 2)
            if len(body) != end - start + 1:
                raise OSError("Truncated or oversized HTTP range response")
            self.bytes_received += len(body)
            return body

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        if whence not in (io.SEEK_SET, io.SEEK_CUR, io.SEEK_END):
            raise ValueError("Invalid seek origin")
        position = offset + {io.SEEK_SET: 0, io.SEEK_CUR: self.pos, io.SEEK_END: self.size}[whence]
        if position < 0:
            raise ValueError("Negative seek position")
        self.pos = position
        return position

    def read(self, size=-1):
        remaining = max(0, self.size - self.pos)
        size = remaining if size is None or size < 0 else min(size, remaining)
        if size > self.max_read:
            raise OSError("Refusing an unbounded archive download")
        if size == 0:
            return b""
        body = self._request(self.pos, self.pos + size - 1)
        self.pos += len(body)
        return body
