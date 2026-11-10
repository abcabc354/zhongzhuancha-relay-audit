# Chat-only 自动回退

> `chat-only` · 脱敏 fixture，不是实时中转数据。

- 协议面：**consistent**
- 可用性：**A (100%)**
- 硬伤：**0**
- 报告：[打开在线报告](https://abcabc354.github.io/relay-audit/demo/scenarios/chat-only/REPORT.html)

## 这是什么

`/responses` 不可用时，工具自动切到 Chat 套件的报告。

## 看哪几个字段

- 模式：chat
- 对话维度：n/a（没有 Responses 的 attribution/final_answer）
- 稳定性/能力/目录仍然计分

## findings

| code | level | 说明 |
|---|---|---|
| `chat.surface` | pass | Chat Completions surface works |
| `chat.stream` | pass | streaming completion finished with content |
| `chat.tools` | pass | Chat function call produced with expected args |
| `chat.structured` | pass | Chat JSON schema output matched |
| `chat.vision` | pass | Chat image input answered correctly |
| `usage.stability` | pass | prompt_tokens stable across repeats |
| `catalog.liveness` | pass | all sampled catalog models answered |
| `identity.undetermined` | info | protocol surface only; model identity is not authenticated |

## 不要误读

- n/a 不是 0 分
- Chat 模式没有 Responses 契约检查，不能拿它证明 Responses 合规

返回：[场景库](index.md) · [Demo](https://abcabc354.github.io/relay-audit/demo/)
