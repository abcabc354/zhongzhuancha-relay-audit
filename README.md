<p align="center">
  <a href="https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/">
    <img src="docs/assets/hero.png" width="760" alt="中转查 · relay-audit">
  </a>
</p>

<h1 align="center">中转查 · relay-audit</h1>

<p align="center">给 OpenAI 兼容中转做一次“能不能用、协议面是否像官方”的体检。</p>

<p align="center">简体中文 ｜ <a href="README.en.md">English</a></p>

<p align="center">
  <a href="https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/"><img src="docs/assets/buttons/demo.svg" height="42" alt="Live demo"></a>
  <a href="https://github.com/abcabc354/zhongzhuancha-relay-audit/releases/latest"><img src="docs/assets/buttons/download.svg" height="42" alt="Download wheel"></a>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="docs/assets/badges/python.svg" alt="Python 3.11+"></a>
  <a href="https://pypi.org/project/zhongzhuancha-relay-audit/"><img src="https://img.shields.io/pypi/v/zhongzhuancha-relay-audit.svg" alt="PyPI"></a>
  <a href="docs/checks.md"><img src="docs/assets/badges/protocol.svg" alt="Responses + Chat"></a>
  <a href="#"><img src="docs/assets/badges/public.svg" alt="public alpha"></a>
  <a href="LICENSE"><img src="docs/assets/badges/license.svg" alt="MIT"></a>
  <a href="https://github.com/abcabc354/zhongzhuancha-relay-audit/actions/workflows/ci.yml"><img src="https://github.com/abcabc354/zhongzhuancha-relay-audit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

<p align="center">
  <img src="docs/assets/demo.gif" width="49%" alt="terminal demo">
  <img src="docs/assets/report-preview-wide.png" width="49%" alt="report preview">
</p>

<p align="center"><em>左：真实命令输出的逐字动画；右：报告预览。主分、协议附录和检查明细分开呈现。</em></p>

## 关于

**中转查**（[zhongzhuancha.com](https://zhongzhuancha.com/)）是一个 AI 中转站导航与评测站。
这个仓库是它的 **clean audit-only** 工具：只回答“能不能用、协议面是否像官方”，不认证型号身份。

- 先探 `/responses`，不支持就自动回退 Chat-only；
- 主分只看稳定性、对话、能力、目录；
- 协议契约、错误码和包装放在附录，作为证据，不直接扣主分；
- 不放 API key、证据或真实报告；完整 legacy `relay_check` 不在这里。

如果这个项目对你有帮助，欢迎点一个 Star :star:。

## 它能回答什么

| 回答 | 不回答 |
|---|---|
| Responses / Chat 面是否可用 | 底层权重是不是某个具体型号 |
| 流式、工具、结构化、视觉是否正常 | 同门型号替换（例如 6-sol 冒充 6.1-sol） |
| 同一请求用量是否稳定 | 服务商是否“官方” |
| 目录里的型号是否真的能调 | 充值/退款/服务承诺 |
| 协议参数是否生效、错误码是否像官方 | — |

## 快速开始

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install zhongzhuancha-relay-audit

zzc-audit --base-url https://relay.example/v1 \
  --api-key-file config/relay-a.local.env \
  --out _evidence/report --enable-remote
```

也可以从源码安装：

```sh
pip install -e .
```

> 兼容：旧的 `relay-audit` / `relay-audit-compare` / `relay-audit-trend` / `relay-inspect` 仍保留；新项目请使用 `zzc-*`。

## 工作流

```mermaid
flowchart LR
    A[中转站] --> B{/responses 可用?}
    B -- 是 --> C[Responses 套件]
    B -- 否 --> D[Chat 套件]
    C --> E[协议 findings]
    D --> E
    E --> F[可用性记分卡]
    F --> G[HTML / Markdown]
    F --> H[对比 / 趋势]
```

## 文档

- [场景库](docs/scenarios/index.md)
- [第一次审计](docs/walkthrough.md)
- [检查项参考](docs/checks.md)
- [评分口径](docs/scoring.md)
- [架构](docs/architecture.md)
- [FAQ](docs/faq.md)
- [示例](docs/examples.md)
- [Roadmap](ROADMAP.md)
- [PyPI 发布](docs/publishing.md)
- [Live demo](https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/)

## 参与

欢迎 issue、PR 和真实脱敏样例。

- [Contributing](.github/CONTRIBUTING.md)
- [Security Policy](.github/SECURITY.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.md)

<p align="center">
  <a href="https://github.com/abcabc354/zhongzhuancha-relay-audit/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=abcabc354/zhongzhuancha-relay-audit" alt="contributors">
  </a>
</p>

## 边界

- 低分不等于型号假，高分也不等于型号真；
- 同门型号替换无法排除；
- 自报、persona、instructions 只能当线索，不能当身份证据。

## License

MIT
