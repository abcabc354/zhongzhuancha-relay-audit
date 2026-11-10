# 示例

在线 Demo：

- [Demo 首页](https://abcabc354.github.io/relay-audit/demo/)
- [单站报告](https://abcabc354.github.io/relay-audit/demo/report.html)
- [多站对比](https://abcabc354.github.io/relay-audit/demo/compare.html)
- [历史趋势](https://abcabc354.github.io/relay-audit/demo/trend.html)

所有样例都是脱敏的 `relay-a` / `relay-b`，不是实时中转数据。

## 单站报告怎么看

1. **先看三张卡**：协议面、可用性、型号身份；
2. **再看记分卡**：稳定性/对话/能力/目录，哪一项 warn；
3. **协议契约和错误码在附录**：它们是证据，不直接扣主分；
4. **最后看检查明细**：每个 code 为什么 pass/warn/fail。

## 一个 92 分的例子

```text
稳定性 2/3 = 67%
对话   4/4 = 100%
能力   4/4 = 100%
目录   1/1 = 100%
overall = 92%
```

原因是稳定性维度只有 3 项，1 个 `usage.stability` warn 就拉低整个维度。不是隐藏权重，也不是协议硬伤扣分。

## Chat-only 目标

`--mode auto` 先探 `/responses`：

- 不可用 → 自动切 Chat 套件；
- 报告里 `mode=chat`，对话维度可能显示 `n/a`；
- 主分仍由稳定性/能力/目录组成。

## 对比和趋势

- 对比：把多份快照放到同一口径，看协议面、可用性、硬伤数；
- 趋势：同一目标多次审计，看覆盖度折线、协议面状态、包装哈希变化。

趋势页不会自动合并不同模式（Responses/Chat）或不同目录策略的数据；需要按系列分开。
