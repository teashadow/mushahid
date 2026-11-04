"""Summarise a mushahid run.

    python3 -m mushahid.summary run.jsonl
"""
import json
import sys
from collections import Counter
from urllib.parse import urlsplit


def main(path):
    evs = Counter()
    hosts = Counter()
    crypto = Counter()
    wasm = 0
    console_levels = Counter()
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            evs[r.get("ev", "?")] += 1
            if r.get("ev") == "req":
                hosts[urlsplit(r.get("u", "")).netloc] += 1
            elif r.get("ev") == "hook" and r.get("kind") == "crypto":
                crypto[r["data"].get("op", "?")] += 1
            elif r.get("ev") == "hook" and r.get("kind") == "wasm":
                wasm += 1
            elif r.get("ev") == "console":
                console_levels[r.get("level", "?")] += 1

    print(f"== {path}")
    for k, v in evs.most_common():
        print(f"  {k:10} {v}")
    print("\ntop hosts:")
    for h, v in hosts.most_common(8):
        print(f"  {v:5}  {h}")
    if crypto:
        print("\ncrypto.subtle ops seen:")
        for op, v in crypto.most_common():
            print(f"  {v:5}  {op}")
    if wasm:
        print(f"\nwasm modules captured: {wasm}")
    if console_levels:
        print("\nconsole levels:")
        for lv, v in console_levels.most_common():
            print(f"  {v:5}  {lv}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "run.jsonl")
