#!/usr/bin/env python3
"""mushahid — مُشَاهِدٌ — the quiet witness.

Not a passive spectator: in the tradition the word describes a witness
whose heart sees through the veil. In that spirit this tool sits under
a browser tab and bears quiet witness to everything the page does —
network bodies, console, crypto keys, wasm modules — writing it all
down without touching anything.

One file, stdlib + websocket-client. Old school.

Usage:
    python3 mushahid.py --port 9224 [--match substring] \
        [--out run.jsonl] [--reload]

The witness sees; it does not touch. Ctrl-C to stop; it prints its tally.
"""
import argparse
import json
import signal
import socket
import sys
import time
import urllib.request


class CDPSock:
    def __init__(self, ws_url):
        import websocket  # websocket-client, the one true old-school dep
        self._ws_mod = websocket
        self.ws = websocket.create_connection(ws_url, max_size=None)
        self._id = 0

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
        except self._ws_mod.WebSocketTimeoutException:
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
  // crypto.subtle — witness the keys before the veil falls
  const subtle = crypto.subtle;
  if (subtle) {
    for (const op of ['encrypt','decrypt','sign','verify','generateKey',
                      'importKey','deriveKey','deriveBits']) {
      const orig = subtle[op].bind(subtle);
      subtle[op] = function(algo, ...rest) {
        const safe = (o) => { try { return JSON.parse(JSON.stringify(o)); }
                              catch (e) { return String(o); } };
        const pk = (k) => { try { return (k && k.extractable && k.type && k.algorithm)
              ? {type: k.type, alg: k.algorithm.name} : String(k); } catch (e) { return '?'; } };
        log('crypto', {op, algo: safe(algo), args: rest.slice(0,2).map(pk)});
        return orig(algo, ...rest);
      };
    }
  }
  // export every generated/imported extractable key (async, quiet)
  const witnessKey = (k) => {
    if (!k || !k.extractable || !k.type) return;
    crypto.subtle.exportKey('raw', k).then(raw => {
      const b = new Uint8Array(raw);
      log('keymat', {kt: k.type, alg: k.algorithm && k.algorithm.name,
        len: b.length, hex: Array.from(b.slice(0, 64)).map(x => x.toString(16).padStart(2,'0')).join('')});
    }).catch(() => {
      crypto.subtle.exportKey('jwk', k).then(jwk => {
        log('keymat', {kt: k.type, alg: k.algorithm && k.algorithm.name, jwk: JSON.stringify(jwk).slice(0, 400)});
      }).catch(() => {});
    });
  };
  for (const op of ['generateKey', 'importKey']) {
    const orig = subtle[op].bind(subtle);
    subtle[op] = function(...a) {
      const r = orig(...a);
      if (r && r.then) r.then(k => {
        (Array.isArray(k) ? k : [k]).forEach(k => k && k.type ? witnessKey(k) : null);
      }).catch(() => {});
      return r;
    };
  }
  // WebAssembly — witness the hidden binary
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
    ap = argparse.ArgumentParser(description="mushahid — the quiet witness")
    ap.add_argument("--port", type=int, default=9224)
    ap.add_argument("--match", default="")
    ap.add_argument("--out", default="run.jsonl")
    ap.add_argument("--reload", action="store_true",
                    help="reload the tab once after attach, so the "
                         "page hooks apply (they live on new documents)")
    args = ap.parse_args()

    tab = find_tab(args.port, args.match)
    print(f"mushahid attached: {tab['url'][:70]}", file=sys.stderr)

    cdp = CDPSock(tab["webSocketDebuggerUrl"])
    cdp.send("Network.enable")
    cdp.send("Runtime.enable")
    cdp.send("Page.enable")
    cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": HOOK_JS})

    url_map = {}   # requestId -> url
    id2rid = {}    # cdp call id -> requestId (pending getResponseBody)
    out = open(args.out, "a", buffering=1)
    t0 = time.time()
    tally = {"req": 0, "resp": 0, "hook": 0, "console": 0, "nav": 0}

    if args.reload:
        cdp.send("Page.reload")
        print("(--reload: page reloaded, hooks planted)", file=sys.stderr)

    stop = {"flag": False}

    def _sig(signum, frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    while not stop["flag"]:
        ev = cdp.next_event()
        if ev is None:
            continue
        m = ev.get("method", "")
        p = ev.get("params", {})
        ts = round(time.time() - t0, 3)

        if m == "Network.requestWillBeSent":
            r = p["request"]
            rid = p["requestId"]
            url_map[rid] = r["url"]
            out.write(json.dumps({"t": ts, "ev": "req", "m": r["method"],
                                  "u": r["url"],
                                  "body": (r.get("postData") or "")[:20000]})
                      + "\n")
            tally["req"] += 1
        elif m == "Network.responseReceived":
            rid = p["requestId"]
            cid = cdp.send("Network.getResponseBody", {"requestId": rid})
            id2rid[cid] = rid
        elif m == "Page.frameNavigated" and not p.get("frame", {}).get("parentId"):
            url = p["frame"].get("url", "")
            if url:
                out.write(json.dumps({"t": ts, "ev": "nav", "u": url}) + "\n")
                tally["nav"] += 1
        elif m == "Runtime.consoleAPICalled":
            txt = " ".join(str(a.get("value", a.get("description", "")))
                           for a in p.get("args", []))
            if txt.startswith("@@moss"):
                _, kind, payload = txt.split(" ", 2)
                out.write(json.dumps({"t": ts, "ev": "hook",
                                      "kind": kind,
                                      "data": json.loads(payload)}) + "\n")
                tally["hook"] += 1
            elif txt.strip():
                out.write(json.dumps({"t": ts, "ev": "console",
                                      "level": p.get("type", ""),
                                      "msg": txt[:500]}) + "\n")
                tally["console"] += 1
        elif "id" in ev and "result" in ev:
            rid = id2rid.pop(ev["id"], None)
            body = (ev["result"] or {}).get("body")
            if rid and body:
                out.write(json.dumps({"t": ts, "ev": "resp",
                                      "u": url_map.get(rid, "?"),
                                      "body": body[:20000]}) + "\n")
                tally["resp"] += 1

    print("witness rests: " +
          " ".join(f"{k}={v}" for k, v in tally.items()), file=sys.stderr)


if __name__ == "__main__":
    main()
