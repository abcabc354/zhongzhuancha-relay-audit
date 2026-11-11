# PyPI 发布

包名：`zhongzhuancha-relay-audit`

当前仓库使用 **PyPI Trusted Publishing**，不需要把 API token 放进 GitHub Secrets。

## 一次性配置

### 1. PyPI 账号

- 注册/登录 https://pypi.org/
- 开启 2FA
- 验证邮箱

### 2. 创建 pending publisher

PyPI → **Publishing** → **Add a new pending publisher**：

| 字段 | 值 |
|---|---|
| PyPI Project Name | `zhongzhuancha-relay-audit` |
| Owner | `abcabc354` |
| Repository name | `zhongzhuancha-relay-audit` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

### 3. GitHub Environment

仓库 → Settings → Environments → New environment：

```text
pypi
```

可以不加保护规则；想人工确认发布就加 Required reviewers。

## 发布

方式 A：发 GitHub Release

```text
Release → Draft a new release → tag v0.2.0 → Publish release
```

`publish.yml` 会自动构建 sdist + wheel 并上传。

方式 B：手动触发

```text
Actions → Publish → Run workflow
```

## 版本规则

- PyPI 同一个版本只能上传一次；
- 改代码后必须升 `pyproject.toml` 的 `version`；
- 不要复用已发布的版本号。

## 验证

发布后：

```sh
pip install zhongzhuancha-relay-audit
zzc-audit --help
python -c "import relay_audit; print(relay_audit.__version__)"
```

## 备选：API token

如果不用 Trusted Publishing，也可以在本地：

```sh
python -m build
python -m twine upload dist/*
```

token 只放本机/密码管理器，不提交到仓库。

## 当前状态

- 0.2.1 已通过 Trusted Publishing 发布（含 Pages SEO meta）。
- 验证：`pip install zhongzhuancha-relay-audit`，然后 `zzc-audit --help`。
