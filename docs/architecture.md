# 架构

```mermaid
flowchart LR
    A[API key / base URL] --> B[normalize + check_base]
    B --> C[/models 目录]
    C --> D{/responses 可用?}
    D -- yes --> E[Responses 套件]
    D -- no --> F[Chat 套件]
    E --> G[findings]
    F --> G
    G --> H[可用性记分卡]
    H --> I[REPORT.html / .md]
    H --> J[compare / trend]
    G --> K[AUDIT/ 证据 + manifest]
```

## 模块

| 文件 | 作用 |
|---|---|
| `protocol_audit.py` | 请求、探测、findings、自动回退 |
| `protocol_scorecard.py` | 维度/覆盖度/附录 |
| `relay_audit.py` | 一条命令：审计 + 记分卡 + HTML |
| `relay_compare.py` | 多份证据对比 |
| `relay_trend.py` | 同一目标历史趋势 |
| `relay_inspect.py` | 配置驱动的每日巡检 |
| `evidence.py` | JSON、hash、0600 写入、manifest |

## 证据目录

```text
AUDIT/
├── PLAN.json
├── RESULTS.json
├── SUMMARY.json
├── REPORT.md
└── manifest.json / manifest.sha256
```

`PLAN` 和 `RESULTS` 会脱敏；key 只从外部 0600 文件读取，不写入证据。

## 身份边界

工具只做协议面/可用性，不做模型身份认证；`identity_undetermined` 是固定信息项。
