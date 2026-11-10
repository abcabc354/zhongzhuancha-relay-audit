# 续接不支持

> `prev-unsupported` · 脱敏 fixture，不是实时中转数据。

- 协议面：**inconsistent**
- 可用性：**A (100%)**
- 硬伤：**1**
- 报告：[打开在线报告](https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/scenarios/prev-unsupported/REPORT.html)

## 这是什么

`previous_response_id` 被 400 拒绝，上下文续接不可用。

## 看哪几个字段

- 主分：A (100%)
- 附录协议契约：previous.roundtrip fail
- 硬伤数：1

## findings

| code | level | 说明 |
|---|---|---|
| `responses.surface` | pass | Responses surface returned a completed response |
| `responses.attribution` | pass | usage.attribution present |
| `responses.reasoning_items` | info | no reasoning item in this short call |
| `responses.final_answer` | pass | message phase=final_answer |
| `wrapper.instructions` | info | no injected instructions |
| `reasoning.scaling` | pass | reasoning tokens increase with effort |
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
| `previous.roundtrip` | fail | previous_response_id rejected as unsupported |

## 不要误读

- 单轮可用不代表多轮续接可用
- 这是协议契约问题，不是模型身份问题

返回：[场景库](index.md) · [Demo](https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/)
