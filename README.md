# openai-imagegen

让 Claude Code、QoderCN 和 Kimi Code 复用本机 Codex 登录及其内置 Imagegen 能力。A shared Agent Skill that lets Claude Code, QoderCN, and Kimi Code reuse the local Codex login and built-in Imagegen capability.

[中文](#中文) | [English](#english)

---

<a id="中文"></a>
## 中文

### 项目简介

`openai-imagegen` 是一座跨 Agent 桥梁。Claude Code、QoderCN 或 Kimi Code 加载这个 Skill 后，会启动本机 `codex exec`，由 Codex 的 System `$imagegen` Skill 调用内置 `image_gen` 工具并把图片保存回当前项目。

```text
Claude / QoderCN / Kimi
          ↓
   openai-imagegen Skill
          ↓
       codex exec
          ↓
Codex System $imagegen → built-in image_gen
```

它使用当前 Codex 登录及其额度，不调用 OpenAI Images API，不需要也不会读取 `OPENAI_API_KEY`。Codex 自身不安装本 Skill，继续使用原生 System `imagegen`。

### 核心能力

- 让非 Codex Agent 通过本机 Codex 登录完成真实生图。
- 支持新图生成、参考图生成、多图编辑和 JSONL 批量任务。
- 每次任务启动独立、临时的 `codex exec` 会话，并显式要求调用 System `$imagegen`。
- 将结果保存到调用方项目的精确路径，并验证 PNG、JPEG 或 WebP 文件签名。
- 默认拒绝覆盖现有图片；完全不接触 API Key、OpenAI SDK 或中转 API。

### 快速开始

#### 环境要求

- macOS 或 Linux
- Python 3.9 或更高版本
- 已安装 Codex CLI
- `codex login status` 显示已通过 ChatGPT 登录

```sh
codex --version
codex login status
```

#### 让你的 Agent 帮你安装（推荐）

复制下面这句话，发送给你正在使用、且支持 Agent Skills 的编程 Agent（例如 Claude Code、QoderCN 或 Kimi Code）：

```text
帮我安装这个 skill：https://github.com/Niall-Young/GenerateIMG-with-codex
```

Agent 应将仓库完整安装到它自己的标准用户级 Skills 目录，并保留 `SKILL.md`、`scripts/` 和 `references/`。安装完成后，可让它执行一次 `--dry-run` 来确认 Skill 已被发现且桥接命令可用。

> 本 Skill 是给非 Codex Agent 调用本机 Codex 生图能力的桥梁。Codex 自身已内置 System `imagegen`，无需安装本 Skill。

#### 使用 SkillManager 安装（可选）

如果你已经在使用 SkillManager，也可以用以下命令同时管理多个 Agent 的安装：

```sh
skillmgr source add https://github.com/Niall-Young/GenerateIMG-with-codex.git \
  --name openai-imagegen
skillmgr skill add openai-imagegen . \
  --name openai-imagegen \
  --agents claude,qodercn,kimi
skillmgr plan
skillmgr sync --apply
```

Codex 不在白名单内。执行同步前应确认 `plan` 只为目标 Agent 创建入口且没有冲突。

### 使用方法

安装后，在目标 Agent 中直接要求生图即可，也可以显式调用：

- Claude Code：`/openai-imagegen 生成一张……`
- QoderCN：`/openai-imagegen 生成一张……`
- Kimi Code：`/skill:openai-imagegen 生成一张……`

Skill 最终运行的桥接命令示例：

```sh
python3 scripts/codex_imagegen.py generate \
  --prompt "一只橘猫坐在未来城市屋顶，电影感夜景，16:9" \
  --out output/imagegen/cat.png
```

编辑已有图片：

```sh
python3 scripts/codex_imagegen.py edit \
  --image input/product.png \
  --prompt "只把背景改成暖灰色，产品、标签和构图保持不变" \
  --out output/imagegen/product-edited.png
```

完整命令和 JSONL 格式见 [`references/cli.md`](references/cli.md)。

### 配置与安全

- 认证只来自 Codex 自己保存的登录状态。
- 不要设置或传递 `OPENAI_API_KEY` 给本 Skill。
- 输出必须位于 `--workspace` 内，默认 workspace 是当前目录。
- `--force` 只有在用户明确要求替换现有图片时才能使用。
- 每次真实生成都会消耗 Codex 登录账户可用额度；`--dry-run` 不生图。

### 项目结构

```text
SKILL.md                    Agent Skill 入口
scripts/codex_imagegen.py   Codex CLI 桥接器
references/                 调用与提示词参考
tests/                      离线桥接测试
```

### 开发与验证

```sh
python3 -m unittest discover -s tests -v
python3 scripts/codex_imagegen.py --help
python3 scripts/codex_imagegen.py generate \
  --prompt "test" \
  --out output/imagegen/test.png \
  --dry-run
```

真实端到端验证必须产生一张可打开的图片，仅有 dry-run 不算完成。

### 许可证

本项目采用 [MIT License](LICENSE)。

[English](#english) · [返回顶部](#openai-imagegen)

---

<a id="english"></a>
## English

### Overview

`openai-imagegen` is a cross-Agent bridge. After Claude Code, QoderCN, or Kimi Code loads the Skill, it starts local `codex exec`; Codex's System `$imagegen` Skill then calls the built-in `image_gen` tool and saves the image back into the current project.

```text
Claude / QoderCN / Kimi
          ↓
   openai-imagegen Skill
          ↓
       codex exec
          ↓
Codex System $imagegen → built-in image_gen
```

It uses the current Codex login and allowance. It does not call the OpenAI Images API and neither requires nor reads `OPENAI_API_KEY`. Codex itself does not receive this Skill and continues using its native System `imagegen`.

### Features

- Let non-Codex Agents perform real image generation through the local Codex login.
- Support new generation, reference-guided generation, multi-image editing, and JSONL batches.
- Start an independent ephemeral `codex exec` session for each task and explicitly require System `$imagegen`.
- Save results to an exact path in the caller's project and validate PNG, JPEG, or WebP signatures.
- Refuse overwrites by default and never use an API key, OpenAI SDK, or relay API.

### Quick Start

#### Prerequisites

- macOS or Linux
- Python 3.9 or newer
- Codex CLI installed
- `codex login status` reports a ChatGPT login

```sh
codex --version
codex login status
```

#### Ask your Agent to install it (recommended)

Copy the prompt below and send it to the Agent Skills-compatible coding Agent you use (for example, Claude Code, QoderCN, or Kimi Code):

```text
Install this skill for me: https://github.com/Niall-Young/GenerateIMG-with-codex
```

The Agent should install the complete repository into its standard user-level Skills directory, preserving `SKILL.md`, `scripts/`, and `references/`. After installation, ask it to run a `--dry-run` to confirm that the Skill is discoverable and the bridge command works.

> This Skill lets non-Codex Agents call the local Codex image-generation capability. Codex already includes the System `imagegen` Skill and does not need this bridge installed.

#### Install with SkillManager (optional)

If you already use SkillManager, you can manage installation across multiple Agents with these commands:

```sh
skillmgr source add https://github.com/Niall-Young/GenerateIMG-with-codex.git \
  --name openai-imagegen
skillmgr skill add openai-imagegen . \
  --name openai-imagegen \
  --agents claude,qodercn,kimi
skillmgr plan
skillmgr sync --apply
```

Codex is not in the allowlist. Before syncing, confirm that `plan` only creates entries for the target Agents and contains no conflicts.

### Usage

After installation, ask the target Agent to generate an image directly or invoke the Skill explicitly:

- Claude Code: `/openai-imagegen generate an image of ...`
- QoderCN: `/openai-imagegen generate an image of ...`
- Kimi Code: `/skill:openai-imagegen generate an image of ...`

Example bridge command ultimately run by the Skill:

```sh
python3 scripts/codex_imagegen.py generate \
  --prompt "An orange cat on a futuristic rooftop, cinematic night scene, 16:9" \
  --out output/imagegen/cat.png
```

Edit an existing image:

```sh
python3 scripts/codex_imagegen.py edit \
  --image input/product.png \
  --prompt "Change only the background to warm gray; preserve the product, label, and composition" \
  --out output/imagegen/product-edited.png
```

See [`references/cli.md`](references/cli.md) for complete commands and the JSONL format.

### Configuration and Security

- Authentication comes only from Codex's stored login state.
- Do not set or pass `OPENAI_API_KEY` to this Skill.
- Outputs must remain inside `--workspace`, which defaults to the current directory.
- Use `--force` only when the user explicitly requests replacement of an existing image.
- Every real generation consumes available Codex account allowance; `--dry-run` creates no image.

### Project Structure

```text
SKILL.md                    Agent Skill entry point
scripts/codex_imagegen.py   Codex CLI bridge
references/                 Invocation and prompting references
tests/                      Offline bridge tests
```

### Development and Verification

```sh
python3 -m unittest discover -s tests -v
python3 scripts/codex_imagegen.py --help
python3 scripts/codex_imagegen.py generate \
  --prompt "test" \
  --out output/imagegen/test.png \
  --dry-run
```

A real end-to-end check must produce a viewable image; a dry run alone is not completion.

### License

This project is available under the [MIT License](LICENSE).

[中文](#中文) · [Back to top](#openai-imagegen)
