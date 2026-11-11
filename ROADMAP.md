# 补齐内容与演示：ROADMAP

## 当前基线

公开仓库已经有：

- README / 英文 README；
- 检查项、评分、架构、FAQ、示例 5 份文档；
- Pages Demo：报告 / 对比 / 趋势；
- CI、Pages、Security、Contributing、Code of Conduct、Issue templates；
- 真实终端输出卡片 + 脱敏报告截图。

缺的不是排版，而是 **可感知的演示、场景库和教程**。

## 与 Hello-Algo 的差距

| 维度 | 差距 |
|---|---|
| 动态演示 | 只有静态终端图，没有 GIF |
| 教程 | 没有“第一次审计怎么走”的 walkthrough |
| 场景 | 只有 relay-a / relay-b，没有失败/壳/漂移案例 |
| 文档站 | 只有 README + 静态 Demo，没有搜索/导航/暗色 |
| 多语言 | 英文只有 README，docs 还是中文 |
| CLI 参考 | 缺完整参数、环境变量、退出码表 |
| 社区证明 | 刚公开，没有真实 stars/contributors/案例 |

## 原则

- 不编造用户评价、stars 或“成功案例”；
- 不把真实中转名、key、证据放进公开仓库；
- 场景全部用**可复现的脱敏 fixture**；
- 能自动生成的内容不手写 HTML；
- 先补“让人 5 分钟看懂”，再补“看起来更大”。

## 阶段与优先级

| 阶段 | 内容 | 产出 | 预估 |
|---|---|---|---|
| P0 | 场景库 + walkthrough | 6 个场景 + 1 篇教程 | 1.5–2 天 |
| P1 | 动态终端 GIF | `docs/assets/demo.gif` | 0.5–1 天 |
| P2 | CLI reference | `docs/cli.md` | 0.5 天 |
| P3 | VitePress 文档站 | 搜索/导航/暗色/i18n | 2–3 天 |
| P4 | 英文文档 + 社区 | English quickstart/checks；真实贡献者 | 2 天+持续 |
| P5 | 品牌视觉/域名 | logo、social preview、`audit.` 子域 | 可选 |

**顺序：P0 → P1 → P2 → P3 → P4。** P5 不阻塞发布。

---

## P0：场景库 + walkthrough

### 场景库

目录：

```text
examples/scenarios/
  responses-good/
  chat-only/
  wrapper-shell/
  cap-ignored/
  prev-unsupported/
  usage-drift/
scripts/build_scenarios.py
docs/scenarios/
  index.md
  responses-good.md
  chat-only.md
  wrapper-shell.md
  cap-ignored.md
  prev-unsupported.md
  usage-drift.md
```

每个 fixture 只放：

- `PLAN.json`
- `SUMMARY.json`
- `RESULTS.json`

全部脱敏：目标名 `relay-a` / `relay-b`，URL `relay-*.example`，不含 key。

`scripts/build_scenarios.py` 用 `zzc-audit --from-audit` 生成到
`docs/demo/scenarios/<slug>/`，不手写报告 HTML。

六个场景：

| slug | 展示什么 | 预期 |
|---|---|---|
| `responses-good` | 正常 Responses | A / consistent |
| `chat-only` | `/responses` 404，自动回退 | `mode=chat`，对话 n/a |
| `wrapper-shell` | 注入 instructions/persona | 主分 A，附录包装 warn/fail |
| `cap-ignored` | `max_output_tokens` 被忽略 | 主分 A，`output.cap` fail |
| `prev-unsupported` | `previous_response_id` 不支持 | 附录 `previous.roundtrip` fail/warn |
| `usage-drift` | 同请求 input_tokens 变化 | 稳定性 warn，总分约 92 |

每个场景文档固定四段：

1. 这是什么；
2. 看哪几个字段；
3. 报告为什么这样判；
4. 不要误读成什么。

### Walkthrough

新增 `docs/walkthrough.md`：

1. 创建 0600 key 文件；
2. `--dry-run` 看计划；
3. 真实审计；
4. 读三张卡 + 记分卡 + 附录；
5. 常见退出码（0 / 2）；
6. Chat-only 例子；
7. `--from-audit` 重出报告；
8. 下一步 compare / trend。

验收：新用户从 README 进入，5 分钟内能跑出第一份报告并知道看哪里。

### P0 验收

- 6 个场景页都能从 `docs/scenarios/index.md` 打开；
- 每个场景有报告链接、findings 解释、误读提醒；
- 全仓库没有真实中转名/key；
- CI 通过；Pages 部署成功；
- README 有 `Walkthrough` 和 `Scenarios` 入口。

---

## P1：动态终端 GIF

工具：

```sh
brew install vhs ffmpeg
```

（当前机器没有 brew/ffmpeg，需要先装；装不上就继续用静态终端卡片，不阻塞 P0。）

新增 `demo/demo.tape`：

```text
Output docs/assets/demo.gif
Set FontSize 14
Set Width 1100
Set Height 560
Set Theme "Dracula"
Type "zzc-audit --from-audit examples/scenarios/responses-good --name relay-a --out demo-report"
Enter
Sleep 3s
Type "ls demo-report"
Enter
Sleep 2s
```

要求：

- 用 fixture，不发真实请求；
- 不出现 key、真实中转名；
- GIF < 5MB，15–20 秒；
- README 中英文都嵌入。

验收：README 首屏能看到“一条命令出报告”的动态过程。

---

## P2：CLI reference

新增 `docs/cli.md`：

- `zzc-audit` 全部参数；
- `zzc-compare` / `zzc-trend` / `zzc-inspect`；
- key 文件字段（`OPENAI_API_KEY` / `OPENAI_BASE_URL`）；
- 环境变量；
- 退出码：
  - 0：完成/一致；
  - 2：协议面 inconsistent，报告仍生成；
- 常见错误：无 base、key 权限不是 0600、输出目录已存在。

验收：每个命令都能从文档直接复制运行。

---

## P3：VitePress 文档站

Hello-Algo 用的是 VitePress，我们也用同一路线：

```text
site/
  .vitepress/config.ts
  index.md
  guide/
  scenarios/
  reference/
```

目标：

- 侧边栏：Guide / Scenarios / Reference / Demo；
- 本地搜索；
- 暗色模式；
- 中文 + English 路由；
- GitHub Pages 部署；
- Demo 仍保留在 `/demo/`。

验收：文档站可搜索、可导航，移动端可读；README 链接到站点。

---

## P4：英文文档 + 社区

- 英文 quickstart、checks、scoring；
- docs 语言切换；
- 真实 contributors / stars / 使用案例（只收真实的）；
- 不编推荐语。

验收：英文用户不看中文 README 也能完成第一次审计。

---

## P5：品牌视觉 / 域名（可选）

- Logo / 简单插画；
- GitHub social preview；
- `audit.zhongzhuancha.com` CNAME；
- 不阻塞前四阶段。

---

## 不做什么

- 不伪造用户评价、stars、案例；
- 不追 6 种语言；
- 不把 Hello-Algo 的书的体量套到工具上；
- 不为了动画而动画。

## Sprint 计划

| Sprint | 内容 | 完成标志 |
|---|---|---|
| S1 | P0 场景库 + walkthrough | 6 个场景 + 5 分钟教程 |
| S2 | P1 GIF + P2 CLI | 动态演示 + 完整参数表 |
| S3 | P3 VitePress | 文档站上线 |
| S4 | P4 英文文档 | 英文路径可用 |

## Definition of Done

- 新用户 5 分钟内跑出第一份报告；
- 至少 6 个可复现场景，含失败/回退/漂移；
- README、文档、Demo 三处互相可达；
- CI/Pages 绿；
- 没有真实 key、中转名或未脱敏证据。
