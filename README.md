# GenLayer ABI Generator

GenLayer contracts are Python, not Solidity. There is no `solc --abi`. This tool parses Python AST, extracts `@gl.public.*` decorators and type annotations, and generates type-safe TypeScript artifacts for the frontend.

## What it generates

| Artifact | File | Purpose |
|---|---|---|
| ABI | `{Contract}Abi.ts` | Typed method map for genlayer-js |
| Hooks | `{Contract}Hooks.ts` | `useContractRead` / `useContractWrite` React hooks |
| Wrapper | `{Contract}Wrapper.ts` | Pre-built client with typed methods |

## Usage

### CLI

```bash
pip install -r requirements.txt

# Inspect parsed ABI
python -m genlayer_abi.cli inspect tests/contracts/sample.py

# Generate TypeScript files
python -m genlayer_abi.cli generate tests/contracts/sample.py \
  --address 0xAbCdEf0123456789 \
  --output-dir ./generated \
  --format all
```

### Web UI

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open `https://genlayer-abi-generator.onrender.com/`. Paste your contract source. It generates on every keystroke.

### API

```bash
curl -X POST https://genlayer-abi-generator.onrender.com/api/generate-ts \
  -H "Content-Type: application/json" \
  -d '{"contract_source":"...", "contract_address":"0x..."}'
```

### VS Code Extension

Install the extension in `vscode-extension/`. Right-click any `.py` contract file → **Generate GenLayer ABI**. Output opens in a side panel with ABI / Hooks / Wrapper tabs.

## Supported types

- Primitives: `str`, `int`, `u256`, `bool`, `float`, `f64`, `bytes`
- Collections: `dict`, `list`, `DynArray[T]`, `TreeMap[K,V]`
- GenLayer: `Address`
- Decorators: `@gl.public.view`, `@gl.public.write`, `@gl.public.write.payable`

## Project layout

```
genlayer_abi/
  parser.py      # AST → ContractAbi
  generator.py   # ContractAbi → TypeScript
  cli.py         # Click CLI
api/
  main.py        # FastAPI endpoints
static/
  index.html     # Web UI
vscode-extension/
  extension.js   # VS Code command + webview
tests/
  contracts/     # Sample .py contracts
```

## GenLayer testnet

- RPC: `https://zksync-os-testnet-genlayer.zksync.dev`
- Chain ID: `4221`
- Explorer: https://zksync-os-testnet-genlayer.explorer.zksync.dev/

MIT
