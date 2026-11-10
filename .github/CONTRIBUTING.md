# Contributing

## Setup

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install httpx pytest
pip install -e .
```

## Tests

```sh
python -m pytest -q
```

## Rules

- 不提交 `config/`、`_evidence/`、API key、真实报告或 `.local.env`；
- 报告/日志里的 URL、账号、请求头必须脱敏；
- 只改 clean audit 子集，不要把 legacy `relay_check` 代码带进来；
- 报告结论只描述协议面/可用性，不要写成“型号真/假”；
- 新增检查项时，同时更新 README 和 `tests/test_audit.py`；
- 一个 PR 只做一件事，并在描述里写清楚命令、报告字段或评分口径。

## Pull requests

- 目标分支：`main`；
- CI 必须通过；
- 如果改了 HTML/报告，附一张脱敏截图或 Live demo 链接。
