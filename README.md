# mushahid — مشاهِد

A tiny old-school observer that sits **under** everything the browser does
and quietly writes down what it saw. No UI, no daemon, no deps beyond Python 3.

```
        ┌─ page ─┐   ┌─ CDP ─┐   ┌─ mushahid ─┐
web ──▶ │  DOM   │ ─▶│Network│ ─▶│  jsonl log │
        └────────┘   └───────┘   └────────────┘
      everything above is loud; everything below is moss
```

## What it records

| layer | how | what you get |
|---|---|---|
| network | CDP `Network.*` | full request/response bodies, timings, headers |
| console | CDP `Runtime.consoleAPICalled` | every log the page tried to hide in verbose |
| crypto | `crypto.subtle` hook (injected) | keys + plaintext **before** encryption |
| wasm | `WebAssembly.compile` hook | every module the page tried to hide |

## Use

```
python3 mushahid.py --port 9224 --match unico --out run.jsonl
```

Then read the run:

```
python3 -m mushahid.summary run.jsonl
```

## Philosophy

Tools that shout get patched. Moss grows quietly.
One file you can read in an afternoon. BSD-2.
