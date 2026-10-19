#!/usr/bin/env python3
"""
Local CORS reverse proxy for Foundry Local.

Why this exists:
  A storyboard web app hosted on GitHub Pages (https://<user>.github.io) needs to
  call Foundry Local's OpenAI-compatible API, which runs on http://127.0.0.1 on this
  Mac. The browser blocks that directly because:
    - Foundry emits no CORS headers (and has no setting to add them), and
    - Chrome/Edge gate "public HTTPS -> localhost" calls behind a Private Network
      Access (PNA) preflight.
  This proxy sits in front of Foundry, adds the CORS + PNA headers, and forwards
  /v1/* straight through (including streaming SSE). Point the app at this proxy.

  It also serves the app files in this folder, so http://127.0.0.1:8757/ opens the
  Video Script Generator with the model API on the same origin -- no separate web
  server, and no CORS at all for that page.

Zero external dependencies: Python 3 stdlib only.
"""

import os
import re
import sys
import json
import threading
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

# Fixed port the app hardcodes. Bind loopback only -- never 0.0.0.0.
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8757

# Model to (re)load automatically if Foundry reports it isn't loaded. Foundry
# evicts idle models and returns HTTP 400 "Model is not loaded" instead of
# loading on demand; the proxy catches that, runs `foundry model load`, and
# retries so the app never sees the error. The model named in the request wins;
# this is only the fallback when a request names none. run-proxy.command passes
# its MODEL through FOUNDRY_DEFAULT_MODEL so the two can't disagree.
LOAD_MODEL = os.environ.get("FOUNDRY_DEFAULT_MODEL") or "qwen3-14b"

# The app files served at http://127.0.0.1:8757/ -- this script's own folder.
APP_DIR = os.path.dirname(os.path.realpath(__file__))  # realpath: macOS /tmp is a symlink
APP_PAGE = "index.html"
_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
    ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".ico": "image/x-icon", ".woff2": "font/woff2",
}

# Strip <think>...</think> reasoning from chat-completion responses before they
# reach the app. Reasoning models (Qwen3) wrap output in these tags, which breaks
# a client that JSON.parse()s the reply. Set False to pass replies through raw.
STRIP_THINK = True

# The app's exact GitHub Pages ORIGIN. For a project site
# (https://<user>.github.io/<repo>) the browser Origin is still just the host:
#   https://<user>.github.io   <-- the /<repo> path is NOT part of the origin.
# >>> SET THIS to your real user/org, e.g. "https://jwalsh.github.io" <<<
APP_ORIGIN = "https://oldgodsslumber.github.io"

# Origins allowed to reach your local model. The app origin above, plus localhost
# for local testing. We echo the matched origin back -- we never use "*", which
# would let ANY website reach your local model.
_LOCALHOST_RE = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")


def origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin == APP_ORIGIN:
        return True
    return bool(_LOCALHOST_RE.match(origin))


# The Host header must name this proxy. Without the check, a web page whose DNS
# name is re-pointed at 127.0.0.1 ("DNS rebinding") becomes same-origin with the
# proxy and can read the app files and drive the model with no CORS check at all.
_ALLOWED_HOSTS = {f"127.0.0.1:{LISTEN_PORT}", f"localhost:{LISTEN_PORT}"}


def host_allowed(host: str) -> bool:
    return (host or "").strip().lower() in _ALLOWED_HOSTS


# Model names go to `foundry model load` as an argv entry (never a shell), but a
# leading "-" would still read as an option, so only plain model ids pass.
_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


# ---------------------------------------------------------------------------
# Foundry endpoint discovery (dynamic -- Foundry picks a new random port on every
# service restart, so we must resolve it at runtime and re-resolve if it moves).
# ---------------------------------------------------------------------------

_endpoint_lock = threading.Lock()
_endpoint_cache = None  # e.g. "http://127.0.0.1:57573"


def _discover_endpoint() -> str:
    # 1) Explicit override wins.
    env = os.environ.get("FOUNDRY_LOCAL_ENDPOINT")
    if env:
        return env.rstrip("/")
    # 2) Ask the CLI. NOTE: the subcommand is `server` on Foundry Local 0.10.x
    #    (older docs say `service`, which no longer exists).
    try:
        out = subprocess.run(
            ["foundry", "server", "status"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception as e:
        raise RuntimeError(f"could not run `foundry server status`: {e}")
    # Newer CLIs print the endpoint as http://localhost:PORT, older ones as
    # http://127.0.0.1:PORT. Either way it's pinned to IPv4 loopback, so
    # "localhost" can't resolve to ::1 first and stall on a refused connect.
    m = re.search(r"https?://(?:127\.0\.0\.1|localhost):\d+", out)
    if not m:
        raise RuntimeError(
            "could not find Foundry endpoint in `foundry server status` output. "
            "Is the Foundry server running?"
        )
    return m.group(0).replace("://localhost:", "://127.0.0.1:")


def get_endpoint(force_refresh: bool = False) -> str:
    global _endpoint_cache
    with _endpoint_lock:
        if force_refresh or _endpoint_cache is None:
            _endpoint_cache = _discover_endpoint()
        return _endpoint_cache


# ---------------------------------------------------------------------------
# <think> stripping
# ---------------------------------------------------------------------------

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_THINK_TAG = re.compile(r"</?think>", re.IGNORECASE)


def strip_think_text(s):
    """Remove <think>...</think> spans (and stray tags) from a whole string."""
    s = _THINK_BLOCK.sub("", s)
    s = _THINK_TAG.sub("", s)
    return s.lstrip()


def strip_think_json(body_bytes):
    """Strip <think> from a non-streaming chat-completion JSON body."""
    data = json.loads(body_bytes.decode("utf-8"))
    for ch in data.get("choices", []):
        for field in ("message", "delta"):
            m = ch.get(field)
            if isinstance(m, dict) and isinstance(m.get("content"), str):
                m["content"] = strip_think_text(m["content"])
    return json.dumps(data).encode("utf-8")


class ThinkFilter:
    """Stateful removal of <think>...</think> across streamed text pieces.

    Tags may be split across chunks, so we buffer a short tail that could be the
    start of a tag and only emit text we're certain sits outside a think block.
    """
    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self):
        self.in_think = False
        self.pending = ""

    @staticmethod
    def _tail(s, tag):
        # longest suffix of s that is a proper prefix of tag (a possible split tag)
        for k in range(min(len(s), len(tag) - 1), 0, -1):
            if s[-k:] == tag[:k]:
                return k
        return 0

    def feed(self, text):
        self.pending += text
        out = []
        while self.pending:
            if not self.in_think:
                i = self.pending.find(self.OPEN)
                if i != -1:
                    out.append(self.pending[:i])
                    self.pending = self.pending[i + len(self.OPEN):]
                    self.in_think = True
                    continue
                keep = self._tail(self.pending, self.OPEN)
                out.append(self.pending[:len(self.pending) - keep])
                self.pending = self.pending[len(self.pending) - keep:]
                break
            else:
                i = self.pending.find(self.CLOSE)
                if i != -1:
                    self.pending = self.pending[i + len(self.CLOSE):]
                    self.in_think = False
                    continue
                self.pending = self.pending[len(self.pending) - self._tail(self.pending, self.CLOSE):]
                break
        return "".join(out)


# ---------------------------------------------------------------------------
# Proxy handler
# ---------------------------------------------------------------------------

# Hop-by-hop headers we must not forward.
_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
    "origin", "referer",
}


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # Quieter logging.
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # --- CORS helpers ------------------------------------------------------
    def _send_cors(self, origin: str):
        if origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Credentials", "true")

    def _reject_bad_host(self):
        if host_allowed(self.headers.get("Host", "")):
            return False
        self.send_error(403, "Unexpected Host header")
        return True

    def do_OPTIONS(self):
        if self._reject_bad_host():
            return
        origin = self.headers.get("Origin", "")
        self.send_response(204)
        self._send_cors(origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        # The critical bit: answer Chrome's Private Network Access preflight.
        # Omit this and the call is blocked with no useful error.
        if self.headers.get("Access-Control-Request-Private-Network") == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self._reject_bad_host():
            return
        if self.path.startswith("/v1/"):
            self._forward()
        else:
            self._serve_static()

    def do_POST(self):
        if self._reject_bad_host():
            return
        self._forward()

    # --- The app's own files -------------------------------------------------
    def _serve_static(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0].split("#", 1)[0])
        if path in ("", "/"):
            self.send_response(302)
            self.send_header("Location", "/" + urllib.parse.quote(APP_PAGE))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        parts = [p for p in path.split("/") if p]
        # No dotfiles or dot-folders (.claude holds local settings), no "..".
        if not parts or any(p.startswith(".") for p in parts):
            self.send_error(404)
            return
        full = os.path.realpath(os.path.join(APP_DIR, *parts))
        ext = os.path.splitext(full)[1].lower()
        if (not full.startswith(APP_DIR + os.sep) or ext not in _STATIC_TYPES
                or not os.path.isfile(full)):
            self.send_error(404)
            return
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", _STATIC_TYPES[ext])
        self.send_header("Content-Length", str(len(data)))
        # Always re-check, so an edited app file shows up on a plain reload.
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # --- Forwarding --------------------------------------------------------
    def _read_body(self):
        length = self.headers.get("Content-Length")
        if length is None:
            return None
        try:
            return self.rfile.read(int(length))
        except (TypeError, ValueError):
            return None

    def _build_upstream_headers(self):
        h = {}
        for k, v in self.headers.items():
            if k.lower() in _HOP_BY_HOP:
                continue
            h[k] = v
        return h

    def _forward(self):
        if not self.path.startswith("/v1/"):
            self.send_error(404, "Only /v1/* is proxied")
            return

        origin = self.headers.get("Origin", "")
        body = self._read_body()
        headers = self._build_upstream_headers()

        did_autoload = False
        # Retries recover from two transient states so the app never sees them:
        #  - Foundry moved its port (connection refused -> re-resolve), and
        #  - the model was evicted (400 "not loaded" -> load it and retry).
        for attempt in range(1, 4):
            base = get_endpoint(force_refresh=(attempt >= 2))
            url = base + self.path
            req = urllib.request.Request(
                url, data=body, headers=headers, method=self.command
            )
            try:
                # Long read timeout: generations can take a while. Connect issues
                # surface as URLError quickly regardless.
                resp = urllib.request.urlopen(req, timeout=600)
                self._relay(resp, resp.status, origin)
                return
            except urllib.error.HTTPError as e:
                err_body = b""
                try:
                    err_body = e.read()
                except Exception:
                    pass
                # Auto-recover from model eviction: load the model once, then retry.
                if (e.code == 400 and not did_autoload
                        and b"not loaded" in err_body.lower()):
                    did_autoload = True
                    if self._load_model(self._requested_model(body)):
                        continue
                # Otherwise relay the error faithfully (status + body).
                self._relay_bytes(e.code, e.headers.get("Content-Type"),
                                  err_body, origin)
                return
            except urllib.error.URLError as e:
                refused = isinstance(e.reason, ConnectionRefusedError)
                if refused and attempt < 3:
                    continue  # re-resolve and retry
                self.send_response(502)
                self._send_cors(origin)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Connection", "close")
                self.end_headers()
                msg = f"Proxy could not reach Foundry Local: {e.reason}\n"
                self.wfile.write(msg.encode())
                return

    @staticmethod
    def _requested_model(body):
        """The model the request asked for, if it's a safe id; else LOAD_MODEL."""
        try:
            name = json.loads(body.decode("utf-8")).get("model")
        except Exception:
            name = None
        if isinstance(name, str) and _MODEL_NAME_RE.match(name):
            return name
        return LOAD_MODEL

    def _load_model(self, name):
        """Load a model into Foundry. Returns True on success."""
        sys.stderr.write(f"Model not loaded -- loading {name} and retrying...\n")
        try:
            r = subprocess.run(
                ["foundry", "model", "load", name],
                capture_output=True, text=True, timeout=180,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _relay_bytes(self, status, ctype, body, origin):
        """Send an already-read response body (used for relayed error responses)."""
        self.send_response(status)
        self._send_cors(origin)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _relay(self, resp, status, origin):
        """Dispatch the upstream response, stripping <think> from chat replies."""
        ctype = resp.headers.get("Content-Type") or ""
        is_chat = "/chat/completions" in self.path
        if STRIP_THINK and is_chat and status == 200:
            low = ctype.lower()
            if "text/event-stream" in low:
                self._relay_sse(resp, status, ctype, origin)
                return
            if "application/json" in low:
                body = b""
                try:
                    body = resp.read()
                finally:
                    try:
                        resp.close()
                    except Exception:
                        pass
                try:
                    body = strip_think_json(body)
                except Exception:
                    pass  # leave body untouched if it isn't the shape we expect
                self._relay_bytes(status, ctype, body, origin)
                return
        self._relay_stream(resp, status, ctype, origin)

    def _relay_stream(self, resp, status, ctype, origin):
        """Stream the upstream response through without buffering (SSE-safe)."""
        self.send_response(status)
        self._send_cors(origin)
        if ctype:
            self.send_header("Content-Type", ctype)
        # No Content-Length: we stream and close so SSE flushes incrementally.
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while True:
                chunk = resp.read(4096)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # client went away mid-stream
        finally:
            try:
                resp.close()
            except Exception:
                pass

    def _relay_sse(self, resp, status, ctype, origin):
        """Stream SSE through, filtering <think> out of each chunk's delta.content."""
        self.send_response(status)
        self._send_cors(origin)
        self.send_header("Content-Type", ctype)
        self.send_header("Connection", "close")
        self.end_headers()
        flt = ThinkFilter()
        try:
            for raw in resp:  # iterate line-by-line (SSE framing preserved)
                line = raw.decode("utf-8", "replace")
                out = line
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload and payload != "[DONE]":
                        try:
                            obj = json.loads(payload)
                            for ch in obj.get("choices", []):
                                d = ch.get("delta")
                                if isinstance(d, dict) and isinstance(d.get("content"), str):
                                    d["content"] = flt.feed(d["content"])
                            out = "data: " + json.dumps(obj) + "\n"
                        except Exception:
                            out = line  # not JSON we understand -- pass through
                self.wfile.write(out.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            try:
                resp.close()
            except Exception:
                pass


def main():
    if APP_ORIGIN.startswith("https://REPLACE-ME"):
        sys.stderr.write(
            "\n[!] APP_ORIGIN is still the placeholder. Edit foundry_cors_proxy.py "
            "and set your real GitHub Pages origin before handing this out.\n\n"
        )
    try:
        ep = get_endpoint()
        ep_note = ep
    except Exception as e:
        ep_note = f"(not resolved yet: {e})"

    print("Foundry Local CORS proxy")
    print(f"  Open the app:                   http://{LISTEN_HOST}:{LISTEN_PORT}/")
    print(f"  Proxy URL (point the app here): http://{LISTEN_HOST}:{LISTEN_PORT}/v1")
    print(f"  Fallback model to auto-load:    {LOAD_MODEL}")
    print(f"  Allowed app origin:             {APP_ORIGIN}")
    print(f"  Forwarding to Foundry at:       {ep_note}")
    print("  Press Ctrl-C to stop.")
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    main()
