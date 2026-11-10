# 第一次审计 walkthrough

目标：5 分钟内跑出第一份报告，并知道看哪里。

## 0. 准备

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install relay_audit-0.1.2-py3-none-any.whl
```

## 1. 建 key 文件

```sh
mkdir -p config
cat > config/relay-a.local.env <<'EOF'
OPENAI_BASE_URL=https://relay.example/v1
OPENAI_API_KEY=REPLACE_ME
EOF
chmod 600 config/relay-a.local.env
```

`relay-audit` 只从 0600 文件或环境变量读 key；不会把 key 写进报告/证据。

## 2. 先 dry-run

```sh
relay-audit \
  --base-url https://relay.example/v1 \
  --api-key-file config/relay-a.local.env \
  --out _evidence/first-run
```

不加 `--enable-remote` 时只打印计划，不发请求。

## 3. 真实审计

```sh
relay-audit \
  --base-url https://relay.example/v1 \
  --api-key-file config/relay-a.local.env \
  --out _evidence/first-run \
  --enable-remote
```

结束后看：

```text
_evidence/first-run/
├── REPORT.html
├── SCORECARD.md
├── SUMMARY.json
└── AUDIT/
```

## 4. 读报告

按顺序看：

1. **三张卡**：协议面、可用性、型号身份；
2. **记分卡**：稳定性 / 对话 / 能力 / 目录；
3. **附录**：包装、协议契约、错误码（不计入主分）；
4. **检查明细**：每个 code 为什么 pass/warn/fail。

常见结论：

- `协议面 inconsistent`：协议契约有 fail，但报告仍然生成；
- `可用性 A`：主分可用，不等于协议完全合规；
- `型号身份 无法判定`：固定值，工具不认证型号身份。

## 5. 退出码

| 退出码 | 含义 |
|---|---|
| 0 | 完成，协议面一致/无硬伤 |
| 2 | 协议面 inconsistent，报告已生成 |

脚本里不要用 `set -e` 把 2 当失败；它表示“报告有硬伤”，不是“没跑”。

## 6. Chat-only 目标

不用手动指定；默认就是 auto：

```sh
relay-audit --base-url https://relay.example/v1 \
  --api-key-file config/relay-a.local.env \
  --out _evidence/chat-only --enable-remote
```

如果 `/responses` 不可用，会自动切 Chat，报告里 `mode=chat`，对话维度可能是 `n/a`。

## 7. 重出报告

```sh
relay-audit --from-audit _evidence/first-run/AUDIT --out _evidence/re-render
```

不发请求，只重新渲染。

## 8. 下一步

- 多目标：[relay-audit-compare](https://github.com/abcabc354/zhongzhuancha-relay-audit#readme)
- 历史趋势：[relay-audit-trend](https://github.com/abcabc354/zhongzhuancha-relay-audit#readme)
- 看不同协议面：[场景库](scenarios/index.md)
- 看报告样例：[Live demo](https://abcabc354.github.io/zhongzhuancha-relay-audit/demo/)
