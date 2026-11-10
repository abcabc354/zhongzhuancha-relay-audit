# 同请求用量漂移

> `usage-drift` · 脱敏 fixture，不是实时中转数据。

- 协议面：**partial**
- 可用性：**A (92%)**
- 硬伤：**0**
- 报告：[打开在线报告](https://abcabc354.github.io/relay-audit/demo/scenarios/usage-drift/REPORT.html)

## 这是什么

同一句 `hi` 两次的 input_tokens 是 9505 和 4387。

## 看哪几个字段

- 稳定性：warn 67% (2/3)
- 总分：A (92%)
- usage.stability 是唯一主分 warn

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
| `store.echo` | pass | store flag echoed as expected |
| `cache.retention` | pass | prompt_cache_retention accepted |
| `text.verbosity` | pass | text.verbosity echoed as low |
| `tools.function_call` | pass | Responses function call produced with expected args |
| `structured.output` | pass | JSON schema output matched |
| `identity.undetermined` | info | protocol surface only; model identity is not authenticated |
| `usage.stability` | warn | same request reports different input_tokens |

## 不要误读

- 92 不是隐藏权重，是小维度覆盖度的结果
- 单次漂移不代表长期不稳定

返回：[场景库](index.md) · [Demo](https://abcabc354.github.io/relay-audit/demo/)
