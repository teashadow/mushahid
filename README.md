# mushahid — مُشَاهِدٌ

> قَدْ بَصَّرْتُمْ إِنْ أَبْصَرْتُمْ
>
> *"You were given sight, if only you would become those who see."*
>
> — Imam Ali, *Nahj al-Balagha*, Saying 208

## On the name

In the Shia tradition, a **mushahid** (مشاهد) is not a passive spectator.
The word describes a witness-contemplator — one whose heart sees through
the veil of the outward world to what is actually there; in the words of
the *Du'a* attributed to Imam Sajjad, a contemplator of the secrets of
being who watches with "the eyes of the spirit."

This tool borrows the name in that spirit and with respect. It is a
secular debugging instrument — one Python file — but it tries to live up
to the word that names it:

- it **watches quietly** (no UI, no daemon, no noise);
- it **sees through veils** — TLS, minification, obfuscation — down to
  the plaintext, the keys, the binary;
- it **bears honest witness** to everything it saw, in a plain `jsonl`
  log that does not lie;
- it **changes nothing** — the witness sees; it does not touch.

If the use of this word troubles anyone: it was chosen as an honor, not
a claim. This is not religious software; it is an engineer's tool that
admires the idea of seeing truly.

```
        ┌─ page ─┐   ┌─ CDP ─┐   ┌─ mushahid ─┐
web ──▶ │  DOM   │ ─▶│Network│ ─▶│  jsonl log │
        └────────┘   └───────┘   └────────────┘
      everything above is loud; everything below is moss
```

## What it records

Sits under a Chrome tab (via the Chrome DevTools Protocol) and writes
one JSON line per event:

| layer | how | what you get |
|---|---|---|
| network | CDP `Network.*` | full request/response bodies, mapped to URLs |
| navigation | CDP `Page.frameNavigated` | every journey of the page |
| console | CDP `Runtime.consoleAPICalled` | every log, incl. verbose the page tried to hide |
| crypto | `crypto.subtle` hook (injected) | algorithm + key params **before** the veil falls |
| wasm | `WebAssembly.compile` hook | every module the page tried to hide, head as base64 |

## Use

```
pip install websocket-client
python3 mushahid.py --port 9224 --match mysite --out run.jsonl --reload
```

`--reload` reloads the tab once after attaching, so the page hooks
(which live on new documents) are planted. Stop with Ctrl-C; it prints
its tally.

Then read the run:

```
python3 -m mushahid.summary run.jsonl
```

## Philosophy

Tools that shout get patched. Moss grows quietly.
The witness sees; it does not touch.

## License

BSD-2-Clause. See [LICENSE](LICENSE).
