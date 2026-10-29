#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tiny caching DD play-line micro-API for the hand viewer.

The viewer never needs this to show a deal: the auction and makeable-tricks grid travel in the
link itself. This service only lights up the double-dummy parts of the play panel (the DD line,
per-card DDS, best line, claim, playing against the double-dummy). It computes lazily (endplay)
and caches to disk (ddline.py), so the first view of a board costs one DDS solve chain
(~10-200 ms) and every later view — any visitor — is a file read. Pure standard library + endplay.

Run (from a venv that has endplay):
    python server/ddserver.py --host 127.0.0.1 --port 8098
Then expose it and point the viewer at it: proxy a public path to this port in nginx, e.g.
    location = /api/ddline { proxy_pass http://127.0.0.1:8098/ddline; }
and add  api=/api/ddline  to every viewer link.

Requests (hands in the viewer's format s<spades>h<hearts>d<diamonds>c<clubs>, c like "3nt"/"4sx",
dl a seat letter):
  GET /ddline?n=&e=&s=&w=&c=&dl=&l=<lead>        the full DD line from the opening lead ("c9",
      optional) -> {"p": ["c7","cA",...], "strain": "H", "declarer": "E", "lead": "C9"}
  GET /ddline?...&played=<k1,k2,...>             DD evaluation of the position after those cards
      -> {"turn": "W", "side": "ew", "best": 5, "cards": {"c7": 5, "ca": 4, ...}}
  GET /ddline?...&played=<k1,k2,...>&line=1      the DD-optimal continuation -> {"p": [...]}
An unusable request (incomplete or illegal deal, bad contract) answers p=[] / cards={}, never 500.
"""
import os, sys, re, json, argparse, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ddline

# endplay's DDS engine is NOT thread-safe — concurrent solve_board calls corrupt its shared state
# and abort the whole process. ThreadingHTTPServer serves requests in parallel, so serialise the
# actual double-dummy work behind one lock. Each call is milliseconds, so throughput is unaffected.
_DDS_LOCK = threading.Lock()


def _parse_hand(s):
    """'s542h8dQ764cK8542' -> {'S':'542','H':'8','D':'Q764','C':'K8542'}."""
    out = {"S": "", "H": "", "D": "", "C": ""}
    cur = None
    for ch in (s or ""):
        u = ch.upper()
        if u in "SHDC":
            cur = u
        elif cur:
            out[cur] += u
    return out


def compute(qs):
    one = lambda k: (qs.get(k, [""])[0] or "")
    hands = {seat.upper(): _parse_hand(one(seat)) for seat in ("n", "e", "s", "w")}
    if not all(any(hands[s].values()) for s in hands):
        return {"p": []}                                   # need all four hands
    m = re.match(r"(\d)(nt|[shdc])", one("c"), re.I)
    if not m:
        return {"p": []}
    strain = "NT" if m.group(2).upper() == "NT" else m.group(2).upper()
    decl = one("dl").upper()[:1]
    # `played` present (even empty) => a mid-play DD evaluation for the position after those cards;
    # absent => the full opening-lead line (cached). keep_blank_values keeps an empty prefix (the
    # opening-lead position) distinguishable from a line request.
    if "played" in qs:
        prefix = [c for c in one("played").lower().split(",") if c]
        if one("line"):                                    # DD-optimal continuation from this position
            return {"p": ddline.line_from_for(hands, strain, decl, prefix)}
        return ddline.eval_for(hands, strain, decl, prefix) or {"cards": {}}
    lead = one("l").upper()
    line = ddline.line_for(hands, strain, decl, lead or None)
    return {"p": line, "strain": strain, "declarer": decl, "lead": lead}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj, cacheable):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        # a solved line is immutable; an unsolved/empty result must not be cached (endplay may just
        # be temporarily off, or the deal may be fixed later)
        self.send_header("Cache-Control",
                         "public, max-age=31536000, immutable" if cacheable else "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.rstrip("/").endswith("ddline") or u.path in ("", "/"):
            try:
                with _DDS_LOCK:
                    obj = compute(parse_qs(u.query, keep_blank_values=True))
                self._send(200, obj, cacheable=bool(obj.get("p") or obj.get("cards")))
            except Exception as e:                          # never 500 the viewer into a broken state
                self._send(200, {"p": [], "error": str(e)}, cacheable=False)
        else:
            self._send(404, {"p": [], "error": "not found"}, cacheable=False)

    do_HEAD = do_GET

    def log_message(self, *a):
        pass                                                # quiet; front it with nginx access logs


def main():
    ap = argparse.ArgumentParser(description="Caching DD play-line micro-API")
    ap.add_argument("--host", default=os.environ.get("DDLINE_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("DDLINE_PORT", "8098")))
    a = ap.parse_args()
    print(f"DD-line API  http://{a.host}:{a.port}/ddline   "
          f"DDS={'on' if ddline.HAVE_DDS else 'OFF (returns empty lines)'}   "
          f"cache={ddline._default_cache_dir()}")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
