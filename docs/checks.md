# 检查项参考

每个 finding 都有 `pass` / `warn` / `fail` / `info`。`info` 不参与可用性主分。

## 主分维度

| 维度 | 检查码 | 说明 |
|---|---|---|
| 稳定性 | `responses.surface` | `/responses` 是否能返回完整响应 |
| 稳定性 | `chat.surface` | `/chat/completions` 是否可用 |
| 稳定性 | `chat.stream` | Chat 流式是否能正常结束并带内容 |
| 稳定性 | `usage.stability` | 同一请求重复时 input/prompt tokens 是否稳定 |
| 对话 | `responses.attribution` | `usage.attribution` 是否存在 |
| 对话 | `responses.final_answer` | message 是否为 `final_answer` |
| 对话 | `cache.retention` | `prompt_cache_retention` 是否被接受 |
| 对话 | `text.verbosity` | `text.verbosity` 是否被接受/回显 |
| 能力 | `image.vision` | 图片输入是否能正确回答 |
| 能力 | `tools.function_call` | 工具调用是否产生预期参数 |
| 能力 | `structured.output` | JSON schema 输出是否匹配 |
| 能力 | `reasoning.scaling` | effort 提高时 reasoning tokens 是否增加 |
| 能力 | `chat.tools` | Chat 工具调用 |
| 能力 | `chat.structured` | Chat JSON schema |
| 能力 | `chat.vision` | Chat 图片输入 |
| 目录 | `catalog.liveness` | `/models` 抽检型号是否可调用 |

## 附录：包装

| 检查码 | 说明 |
|---|---|
| `wrapper.instructions` | 是否注入 instructions，长度/哈希 |
| `wrapper.persona` | 注入内容是否声明 Codex/GPT-5 等 persona |
| `wrapper.shared` | 不同模型标签是否共用同一套 instructions |

## 附录：协议契约

| 检查码 | 说明 |
|---|---|
| `output.cap` | `max_output_tokens` 是否真的生效 |
| `previous.roundtrip` | `previous_response_id` 是否能续接上下文 |
| `invalid.parameter` | 非法 `reasoning.effort` 是否被 400 拒绝 |
| `store.echo` | `store` 标记是否按预期回显 |

## 附录：错误码

| 检查码 | 说明 |
|---|---|
| `error.invalid_model` | 非法 model 是否返回官方形状的 400 |
| `error.invalid_cap` | `max_output_tokens=0` 是否被拒绝 |
| `error.unauthorized` | 缺少凭据是否返回 auth 错误 |

## 只记录、不评分

| 检查码 | 说明 |
|---|---|
| `responses.reasoning_items` | 短请求里是否出现 reasoning item |
| `identity.undetermined` | 固定信息项：工具不认证型号身份 |
