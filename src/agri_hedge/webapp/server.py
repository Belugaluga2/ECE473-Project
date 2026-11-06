"""Milestone 2, week 5: a small web server for the farmer screen (standard library only).

Run:   python scripts/run_app.py            then open http://localhost:8473

Routes
  GET  /                 the farmer screen (static/index.html)
  GET  /api/stations     Kalshi monthly-rain stations with rain records
  GET  /api/coverage     PRF grid centers the app can serve (for the map)
  POST /api/quote        JSON body -> agri_hedge.platform.quote(...)
  POST /api/companion    JSON body -> agri_hedge.platform.companion(...) (PRF Companion mode)
"""
from __future__ import annotations

import argparse
import json
import math
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agri_hedge import platform as pf
from agri_hedge import comparison

STATIC = Path(__file__).resolve().parent / "static"
_COVERAGE_CACHE: list | None = None


def _clean(o):
    """Replace NaN/inf (not valid JSON) with None, recursively; numpy scalars become Python numbers."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, "item") and not hasattr(o, "__len__"):
        o = o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


class Handler(BaseHTTPRequestHandler):
    server_version = "AgriHedge/0.2"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        body = json.dumps(_clean(obj), default=pf.json_default, allow_nan=False)
        self._send(code, body.encode(), "application/json")

    def do_GET(self):  # noqa: N802
        global _COVERAGE_CACHE
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path in ("/compare", "/compare.html"):
            return self._send(200, (STATIC / "compare.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/api/farms":
            return self._json(200, comparison.farms())
        if path == "/api/stations":
            return self._json(200, pf.stations())
        if path == "/api/coverage":
            if _COVERAGE_CACHE is None:
                _COVERAGE_CACHE = pf.coverage_points()
            return self._json(200, _COVERAGE_CACHE)
        return self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        route = self.path.split("?", 1)[0]
        handlers = {"/api/quote": pf.quote, "/api/companion": pf.companion,
                    "/api/compare": comparison.compare}
        if route not in handlers:
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            params = json.loads(self.rfile.read(n) or b"{}")
            return self._json(200, handlers[route](params))
        except ValueError as exc:
            return self._json(400, {"error": str(exc)})
        except Exception as exc:  # report, keep serving
            traceback.print_exc()
            return self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    def log_message(self, fmt, *args):
        print("[app]", fmt % args, flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the AgriHedge farmer screen")
    ap.add_argument("--port", type=int, default=8473)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"AgriHedge running on http://{a.host}:{a.port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
