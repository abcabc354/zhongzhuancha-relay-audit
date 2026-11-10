# 场景库

全部为脱敏 fixture，不是实时中转数据。

| 场景 | 说明 | 协议面 | 可用性 | 硬伤 |
|---|---|---|---|---|
| [正常 Responses](responses-good.md) | `responses-good` | consistent | A (100%) | 0 |
| [Chat-only 自动回退](chat-only.md) | `chat-only` | consistent | A (100%) | 0 |
| [Responses 壳](wrapper-shell.md) | `wrapper-shell` | partial | A (100%) | 0 |
| [cap 被忽略](cap-ignored.md) | `cap-ignored` | inconsistent | A (100%) | 1 |
| [续接不支持](prev-unsupported.md) | `prev-unsupported` | inconsistent | A (100%) | 1 |
| [同请求用量漂移](usage-drift.md) | `usage-drift` | partial | A (92%) | 0 |

报告在线地址：<https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/scenarios/>
