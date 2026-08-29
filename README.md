# openai-imagegen

让 Claude Code、QoderCN 和 Kimi Code 通过同一 Agent Skill 调用官方 OpenAI GPT Image 2 API。A shared Agent Skill that lets Claude Code, QoderCN, and Kimi Code use the official OpenAI GPT Image 2 API.

[中文](#中文) | [English](#english)

---

<a id="中文"></a>
## 中文

### 项目简介

`openai-imagegen` 是一份可移植的 Agent Skill，为没有内置 OpenAI 生图工具的代码 Agent 提供文生图、多图编辑和 JSONL 批量生成能力。它调用官方 `gpt-image-2` API，并由本地 SkillManager 按 Agent 白名单分发。

Codex 已有 System-owned `imagegen`，因此本项目的默认白名单只包含 Claude Code、QoderCN 和 Kimi Code，不覆盖 Codex 内置能力。

### 核心能力

- 使用官方 `gpt-image-2` 完成生成和编辑。
- 支持同提示词多变体，以及不同提示词的并发 JSONL 批量任务。
- 输出前检查目标文件，默认不覆盖；批量失败会保留成功结果并返回结构化摘要。
- 只从 `OPENAI_API_KEY` 读取认证，不支持中转 Base URL 或模型降级。
- 使用 Agent Skills 标准的 `SKILL.md + scripts/ + references/` 结构。

### 快速开始

#### 环境要求

- macOS 或 Linux
- [`uv`](https://docs.astral.sh/uv/) 0.10 或更高版本
- 可访问 OpenAI API 的网络
- 拥有 GPT Image API 权限的 `OPENAI_API_KEY`

#### 配置密钥

```sh
export OPENAI_API_KEY="your_api_key_here"
```

密钥只应存在于进程环境中。不要把真实密钥写入仓库、提示词或命令参数。

#### 使用 SkillManager 安装

```sh
skillmgr source add https://github.com/Niall-Young/GenerateIMG-with-codex.git \
  --name openai-imagegen
skillmgr skill add openai-imagegen . \
  --name openai-imagegen \
  --agents claude,qodercn,kimi
skillmgr plan
skillmgr sync --apply
```

执行 `sync --apply` 前检查 `plan`，确认没有意外删除或冲突。若 `skillmgr` 不在 PATH，可在 SkillManager 项目中用 `node dist/cli.js` 替代。

### 使用方法

安装后，可以让 Agent 自动选择 Skill，也可以显式调用：

- Claude Code：`/openai-imagegen`
- QoderCN：`/openai-imagegen`
- Kimi Code：`/skill:openai-imagegen`

直接运行 CLI：

```sh
uv run --script scripts/openai_imagegen.py generate \
  --prompt "A quiet editorial photograph of a ceramic cup at dawn" \
  --size 1024x1024 \
  --quality low \
  --out output/imagegen/cup.png
```

编辑图片：

```sh
uv run --script scripts/openai_imagegen.py edit \
  --image input/product.png \
  --prompt "Replace only the background; keep the product unchanged" \
  --out output/imagegen/product-edited.png
```

完整参数和 JSONL 批量格式见 [`references/cli.md`](references/cli.md)。

### 配置

模型固定为 `gpt-image-2`。默认尺寸为 `auto`、质量为 `medium`、格式为 PNG。CLI 不提供 `--model`、`--base-url` 或自动透明背景降级。

### 项目结构

```text
SKILL.md                    Agent Skill 入口
scripts/openai_imagegen.py  官方 API CLI
references/                 CLI 与提示词参考
tests/                      离线单元测试
```

### 开发与验证

```sh
uv run --python 3.12 python -m unittest discover -s tests -v
uv run --script scripts/openai_imagegen.py --help
uv run --script scripts/openai_imagegen.py generate \
  --prompt "test" \
  --size 1024x1024 \
  --quality low \
  --out output/imagegen/test.png \
  --dry-run
```

`--dry-run` 不访问 API，也不会创建图片，不能替代真实端到端验收。

### 许可证

本项目采用 [MIT License](LICENSE)。

[English](#english) · [返回顶部](#openai-imagegen)

---

<a id="english"></a>
## English

### Overview

`openai-imagegen` is a portable Agent Skill that gives coding agents without a built-in OpenAI image tool text-to-image generation, multi-image editing, and JSONL batch generation. It calls the official `gpt-image-2` API and is distributed through a local SkillManager Agent allowlist.

Codex already owns a System `imagegen` Skill, so this project's default allowlist contains only Claude Code, QoderCN, and Kimi Code and does not replace Codex's built-in capability.

### Features

- Generate and edit images with the official `gpt-image-2` model.
- Create same-prompt variants or run concurrent JSONL jobs for distinct prompts.
- Refuse overwrites by default; retain successful batch results and return a structured failure summary.
- Read authentication only from `OPENAI_API_KEY`, with no relay Base URL or model downgrade.
- Follow the Agent Skills `SKILL.md + scripts/ + references/` structure.

### Quick Start

#### Prerequisites

- macOS or Linux
- [`uv`](https://docs.astral.sh/uv/) 0.10 or newer
- Network access to the OpenAI API
- An `OPENAI_API_KEY` with GPT Image API access

#### Configure the key

```sh
export OPENAI_API_KEY="your_api_key_here"
```

Keep the key only in the process environment. Never place a real key in the repository, prompt, or command arguments.

#### Install with SkillManager

```sh
skillmgr source add https://github.com/Niall-Young/GenerateIMG-with-codex.git \
  --name openai-imagegen
skillmgr skill add openai-imagegen . \
  --name openai-imagegen \
  --agents claude,qodercn,kimi
skillmgr plan
skillmgr sync --apply
```

Inspect `plan` for unexpected removals or conflicts before running `sync --apply`. If `skillmgr` is not on PATH, use `node dist/cli.js` from the SkillManager project instead.

### Usage

After installation, let the Agent select the Skill automatically or invoke it explicitly:

- Claude Code: `/openai-imagegen`
- QoderCN: `/openai-imagegen`
- Kimi Code: `/skill:openai-imagegen`

Run the CLI directly:

```sh
uv run --script scripts/openai_imagegen.py generate \
  --prompt "A quiet editorial photograph of a ceramic cup at dawn" \
  --size 1024x1024 \
  --quality low \
  --out output/imagegen/cup.png
```

Edit an image:

```sh
uv run --script scripts/openai_imagegen.py edit \
  --image input/product.png \
  --prompt "Replace only the background; keep the product unchanged" \
  --out output/imagegen/product-edited.png
```

See [`references/cli.md`](references/cli.md) for all options and the JSONL batch format.

### Configuration

The model is fixed to `gpt-image-2`. Defaults are `size=auto`, `quality=medium`, and PNG output. The CLI intentionally has no `--model`, `--base-url`, or automatic transparent-background downgrade.

### Project Structure

```text
SKILL.md                    Agent Skill entry point
scripts/openai_imagegen.py  Official API CLI
references/                 CLI and prompting references
tests/                      Offline unit tests
```

### Development and Verification

```sh
uv run --python 3.12 python -m unittest discover -s tests -v
uv run --script scripts/openai_imagegen.py --help
uv run --script scripts/openai_imagegen.py generate \
  --prompt "test" \
  --size 1024x1024 \
  --quality low \
  --out output/imagegen/test.png \
  --dry-run
```

`--dry-run` makes no API call and creates no image, so it is not a substitute for live end-to-end validation.

### License

This project is available under the [MIT License](LICENSE).

[中文](#中文) · [Back to top](#openai-imagegen)
