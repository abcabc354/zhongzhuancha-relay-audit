# Responses 壳

> `wrapper-shell` · 脱敏 fixture，不是实时中转数据。

- 协议面：**partial**
- 可用性：**A (100%)**
- 硬伤：**0**
- 报告：[打开在线报告](https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/scenarios/wrapper-shell/REPORT.html)

## 这是什么

主分仍然 A，但注入的 instructions/persona 在附录里被标记。

## 看哪几个字段

- 主分：A (100%)
- 附录包装：warn
- instructions 长度和 persona 只作线索

## findings

| code | level | 说明 |
|---|---|---|
| `responses.surface` | pass | Responses surface returned a completed response |
| `responses.attribution` | pass | usage.attribution present |
| `responses.reasoning_items` | info | no reasoning item in this short call |
| `responses.final_answer` | pass | message phase=final_answer |
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
| `wrapper.instructions` | info | relay injects 21334 chars of instructions |
| `wrapper.persona` | warn | injected instructions declare Codex/GPT-5 persona |
| `wrapper.shared` | warn | model labels use the same injected instructions |

## 不要误读

- 主分 A 不代表没有壳
- instructions 只能当线索，不能当身份证据

返回：[场景库](index.md) · [Demo](https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/)
