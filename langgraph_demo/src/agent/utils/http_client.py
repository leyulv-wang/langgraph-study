from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class HttpResponse:
    status: int
    headers: Dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def _headers_to_dict(headers) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in headers.items():
        out[str(k).lower()] = str(v)
    return out


def request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    timeout_sec: int = 20,
    retries: int = 3,
    retry_backoff_sec: float = 0.8,
    retry_statuses: Tuple[int, ...] = (429, 500, 502, 503, 504),
) -> HttpResponse:
    req = urllib.request.Request(url, data=data, method=method.upper())
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                body = resp.read()
                return HttpResponse(
                    status=int(resp.status),
                    headers=_headers_to_dict(resp.headers),
                    body=body,
                )
        except urllib.error.HTTPError as e:
            status = int(getattr(e, "code", 0) or 0)
            body = e.read() if hasattr(e, "read") else b""
            if attempt >= retries or status not in retry_statuses:
                return HttpResponse(
                    status=status or 0,
                    headers=_headers_to_dict(getattr(e, "headers", {})),
                    body=body,
                )
        except Exception:
            if attempt >= retries:
                raise

        attempt += 1
        time.sleep(retry_backoff_sec * (2 ** (attempt - 1)))

