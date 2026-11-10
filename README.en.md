<p align="center">
  <a href="https://abcabc354.github.io/relay-audit/demo/">
    <img src="docs/assets/hero.png" width="760" alt="Zhongzhuancha · relay-audit">
  </a>
</p>

<h1 align="center">Zhongzhuancha · relay-audit</h1>

<p align="center">A clean audit-only toolkit for OpenAI-compatible relays: does it work, and does the protocol surface look official?</p>

<p align="center">English ｜ <a href="README.md">中文</a></p>

<p align="center">
  <a href="https://abcabc354.github.io/relay-audit/demo/"><img src="docs/assets/buttons/demo.svg" height="42" alt="Live demo"></a>
  <a href="https://github.com/abcabc354/relay-audit/releases/latest"><img src="docs/assets/buttons/download.svg" height="42" alt="Download wheel"></a>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="docs/assets/badges/python.svg" alt="Python 3.11+"></a>
  <a href="docs/checks.md"><img src="docs/assets/badges/protocol.svg" alt="Responses + Chat"></a>
  <a href="#"><img src="docs/assets/badges/public.svg" alt="public alpha"></a>
  <a href="LICENSE"><img src="docs/assets/badges/license.svg" alt="MIT"></a>
  <a href="https://github.com/abcabc354/relay-audit/actions/workflows/ci.yml"><img src="https://github.com/abcabc354/relay-audit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

<p align="center">
  <img src="docs/assets/terminal-demo.png" width="49%" alt="terminal demo">
  <img src="docs/assets/report-preview-wide.png" width="49%" alt="report preview">
</p>

<p align="center"><em>Left: real command output. Right: report preview. Usability score, protocol appendix and check details are separate.</em></p>

## About

**Zhongzhuancha** ([zhongzhuancha.com](https://zhongzhuancha.com/)) is an AI relay directory and review site.
This repository is its **clean audit-only** toolkit: it answers “does it work, and does the protocol surface look official?” It does not authenticate model identity.

- Probes `/responses` first and falls back to Chat-only;
- main score covers stability, dialogue, capability and catalog;
- protocol contracts, error shapes and wrapper details live in the appendix;
- no API keys, evidence or real reports are bundled; the full legacy `relay_check` toolkit is not included.

If this project helps you, a Star :star: is appreciated.

## What it answers

| Answers | Does not answer |
|---|---|
| Is the Responses / Chat surface usable? | Which exact model weights are behind it |
| Do streaming, tools, structured output and vision work? | Same-family model swaps (e.g. 6-sol for 6.1-sol) |
| Is usage stable across identical requests? | Whether the provider is “official” |
| Are catalog models actually callable? | Billing, refunds or service guarantees |
| Do protocol parameters work; do error shapes look official? | — |

## Quick start

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install relay_audit-0.1.2-py3-none-any.whl

relay-audit --base-url https://relay.example/v1 \
  --api-key-file config/relay-a.local.env \
  --out _evidence/report --enable-remote
```

Or from source:

```sh
pip install -e .
```

## Workflow

```mermaid
flowchart LR
    A[Target relay] --> B{/responses available?}
    B -- yes --> C[Responses suite]
    B -- no --> D[Chat suite]
    C --> E[protocol findings]
    D --> E
    E --> F[usability scorecard]
    F --> G[HTML / Markdown]
    F --> H[compare / trend]
```

## Docs

Docs are in Chinese for now:

- [Scenarios](docs/scenarios/index.md)
- [Walkthrough](docs/walkthrough.md)
- [Checks](docs/checks.md)
- [Scoring](docs/scoring.md)
- [Architecture](docs/architecture.md)
- [FAQ](docs/faq.md)
- [Examples](docs/examples.md)
- [Roadmap](ROADMAP.md)
- [Live demo](https://abcabc354.github.io/relay-audit/demo/)

## Contributing and security

- [Contributing](.github/CONTRIBUTING.md)
- [Security Policy](.github/SECURITY.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.md)

<p align="center">
  <a href="https://github.com/abcabc354/relay-audit/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=abcabc354/relay-audit" alt="contributors">
  </a>
</p>

## Scope

- A low score does not mean a model is fake; a high score does not prove it is genuine;
- same-family model swaps cannot be excluded;
- self-reported persona/instructions are clues, not identity evidence.

## License

MIT
