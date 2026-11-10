# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |
| < 0.1 | no |

## Reporting a vulnerability

请使用 GitHub 的 **private vulnerability reporting** 私密报告：

**https://github.com/abcabc354/relay-audit/security/advisories/new**

不要开公开 issue，也不要在 issue/PR 中粘贴 API key、cookie、完整请求头或 `.local.env` 内容。

报告时请尽量包含：

- 影响的版本和入口（`relay-audit` / compare / trend / inspect）；
- 复现步骤；
- 是否涉及密钥、证据目录或报告泄漏；
- 最小化的脱敏日志。

## Scope

重点关注：

- API key 或凭据进入报告、日志、证据目录；
- `AUDIT/` 证据目录或 `REPORT.html` 泄漏本地路径/凭据；
- 报告 HTML 注入或恶意内容执行；
- `--out` / `--from-audit` 路径穿越或覆盖；
- 依赖/构建链问题。

## Out of scope

以下不属于安全漏洞：

- 某个中转不可用、限流或协议行为异常；
- 审计结论“像/不像官方”的争议；
- 型号身份判断的准确性（工具不认证型号身份）。

## Response

这是个人维护项目，按 best effort 处理，不承诺固定 SLA。确认后会尽快发布修复和说明。
