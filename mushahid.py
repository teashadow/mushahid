#!/usr/bin/env python3
"""mushahid — مشاهِد — the quiet observer.

Sits under a Chrome (CDP) tab and records everything:
network bodies, console, crypto keys/plaintext, wasm modules.
One file, stdlib only. Old school.

Usage:
    python3 mushahid.py --port 9224 [--match substring] [--out run.jsonl]
"""
import argparse
import base64
import json
import os
import socket
import sys
import time
import urllib.request

# --- tiny CDP client (no deps) ----------------------------------------

class CDPSock:
    def __init__(self, ws_url):
        import websocket  # websocket-client, the one true old-school dep
        self.ws = websocket.create_connection(ws_url, max_size=None)
        self._id = 0
        self.handlers = {}

    def send(self, method, params=None):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method,
                                 "params": params or {}}))
        return self._id

    def next_event(self, timeout=1.0):
        self.ws.settimeout(timeout)
        try:
            return json.loads(self.ws.recv())
        except socket.timeout:
            return None


def find_tab(port, match):
    tabs = json.loads(urllib.request.urlopen(
        f"http://127.0.0.1:{port}/json/list").read())
    pages = [t for t in tabs if t.get("type") == "page"]
    if match:
        pages = [t for t in pages if match in t.get("url", "")]
    if not pages:
        sys.exit("no matching tab; open one first")
    return pages[0]


# --- the hook: injected before page scripts ---------------------------

HOOK_JS = r"""
(() => {
  if (window.__mushahid) return;
  window.__mushahid = true;
  const log = (kind, data) => {
    try { console.debug('@@moss ' + kind + ' ' + JSON.stringify(data)); }
    catch (e) {}
  };
  // crypto.subtle
  const subtle = crypto.subtle;
  if (subtle) {
    for (const op of ['encrypt','decrypt','sign','verify','generateKey',
                      'importKey','deriveKey','deriveBits']) {
      const orig = subtle[op].bind(subtle);
      subtle[op] = function(algo, ...rest) {
        const safe = (o) => { try { return JSON.parse(JSON.stringify(o)); }
                              catch (e) { return String(o); } };
        log('crypto', {op, algo: safe(algo)});
        return orig(algo, ...rest);
      };
    }
  }
  // WebAssembly
  const wc = WebAssembly.compile.bind(WebAssembly);
  WebAssembly.compile = function(buf) {
    try {
      const bytes = new Uint8Array(buf.buffer || buf);
      const head = bytes.slice(0, 8192);
      log('wasm', {size: bytes.length,
        b64: btoa(String.fromCharCode(...head))});
    } catch (e) {}
    return wc(buf);
  };
})();
"""


def main():
    ap = argparse.ArgumentParser(description="mushahid — the quiet observer")
    ap.add_argument("--port", type=int, default=9224)
    ap.add_argument("--match", default="")
    ap.add_argument("--out", default="run.jsonl")
    args = ap.parse_args()

    tab = find_tab(args.port, args.match)
    print(f"mushahid attached: {tab['url'][:70]}", file=sys.stderr)

    cdp = CDPSock(tab["webSocketDebuggerUrl"])
    cdp.send("Network.enable")
    cdp.send("Runtime.enable")
    cdp.send("Page.enable")
    cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK_JS})

    bodies = {}      # requestId -> base64 body
    out = open(args.out, "a", buffering=1)
    t0 = time.time()

    while True:
        ev = cdp.next_event()
        if ev is None:
            continue
        m = ev.get("method", "")
        p = ev.get("params", {})
        ts = round(time.time() - t0, 3)

        if m == "Network.requestWillBeSent":
            r = p["request"]
            if r.get("postData"):
                bodies[p["requestId"]] = r["postData"]
            out.write(json.dumps({"t": ts, "ev": "req", "m": r["method"],
                                  "u": r["url"],
                                  "body": (r.get("postData") or "")[:4000]})
                      + "\n")
        elif m == "Network.responseReceived":
            rid = p["requestId"]
            cdp.send("Network.getResponseBody", {"requestId": rid})
            bodies.setdefault(rid, None)
        elif m == "Network.loadingFinished":
            rid = p["requestId"]
            if rid in bodies and bodies[rid] is not None:
                out.write(json.dumps({"t": ts, "ev": "resp",
                                      "u": "?", "body": bodies[rid][:4000]})
                          + "\n")
                del bodies[rid]
        elif m == "Runtime.consoleAPICalled":
            txt = " ".join(str(a.get("value", a.get("description", "")))
                           for a in p.get("args", []))
            if txt.startswith("@@moss"):
                _, kind, payload = txt.split(" ", 2)
                out.write(json.dumps({"t": ts, "ev": "hook",
                                      "kind": kind,
                                      "data": json.loads(payload)}) + "\n")
            elif txt.strip():
                out.write(json.dumps({"t": ts, "ev": "console",
                                      "level": p.get("type", ""),
                                      "msg": txt[:500]}) + "\n")
        elif ev.get("id") and "result" in ev:
            body = ev["result"].get("body")
            if body:
                out.write(json.dumps({"t": ts, "ev": "resp",
                                      "u": "?",
                                      "body": body[:4000]}) + "\n")


if __name__ == "__main__":
    main()
