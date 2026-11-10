# 正常 Responses

> `responses-good` · 脱敏 fixture，不是实时中转数据。

- 协议面：**consistent**
- 可用性：**A (100%)**
- 硬伤：**0**
- 报告：[打开在线报告](https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/scenarios/responses-good/REPORT.html)

## 这是什么

一个主维度和协议契约都通过的正常 Responses 快照。

## 看哪几个字段

- 协议面：consistent
- 可用性：A (100%)
- 稳定性/对话/能力/目录都是 100%

## findings

| code | level | 说明 |
|---|---|---|
| `responses.surface` | pass | Responses surface returned a completed response |
| `responses.attribution` | pass | usage.attribution present |
| `responses.reasoning_items` | info | no reasoning item in this short call |
| `responses.final_answer` | pass | message phase=final_answer |
| `wrapper.instructions` | info | no injected instructions |
| `reasoning.scaling` | pass | reasoning tokens increase with effort |
| `previous.roundtrip` | pass | previous_response_id roundtrip works |
| `invalid.parameter` | pass | invalid reasoning.effort rejected as invalid_request_error |
| `error.invalid_model` | pass | invalid model rejected with an official-looking error |
| `error.invalid_cap` | pass | max_output_tokens=0 rejected as invalid_request_error |
| `error.unauthorized` | pass | missing credential rejected with an auth error |
| `output.cap` | pass | max_output_tokens honored |
| `image.vision` | pass | image input answered correctly |
| `chat.surface` | pass | Chat Completions surface works |
| `catalog.liveness` | pass | all sampled catalog models answered |
| `usage.stability` | pass | input_tokens stable across repeats |
| `store.echo` | pass | store flag echoed as expected |
| `cache.retention` | pass | prompt_cache_retention accepted |
| `text.verbosity` | pass | text.verbosity echoed as low |
| `tools.function_call` | pass | Responses function call produced with expected args |
| `structured.output` | pass | JSON schema output matched |
| `identity.undetermined` | info | protocol surface only; model identity is not authenticated |

## 不要误读

- consistent 不代表底层权重是真的
- A 只说明可用性，不说明协议完全合规

返回：[场景库](index.md) · [Demo](https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/)
