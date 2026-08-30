---
name: openai-imagegen
description: Generate or edit raster images by delegating to the locally logged-in Codex CLI and its System imagegen tool. Use when Claude Code, QoderCN, Kimi Code, or another non-Codex Agent needs Codex image generation without an OPENAI_API_KEY. Requires a logged-in Codex CLI. Do not use an OpenAI SDK, direct Images API, or API key.
metadata:
  version: "2.0.0"
  backend: "codex-system-imagegen"
---

# Codex Imagegen Bridge

Use the bundled bridge to ask the locally logged-in Codex CLI to invoke its System `$imagegen` Skill and built-in `image_gen` tool. This consumes the user's Codex login allowance; it does not call the OpenAI Images API directly and does not require `OPENAI_API_KEY`.

## Non-negotiable execution path

```text
current Agent -> this Skill -> scripts/codex_imagegen.py -> codex exec -> System $imagegen -> built-in image_gen
```

- Always use the bundled bridge. Do not recreate the workflow with an SDK, `curl`, an API key, SVG, Python drawing, HTML, CSS, or placeholders.
- Never request, inspect, or store `OPENAI_API_KEY`.
- Require `codex login status` to succeed. If Codex is missing or logged out, tell the user to install or log in to Codex.
- A real request uses Codex allowance. A dry run proves routing only and is not completed image generation.
- Do not claim success until the requested bitmap exists at the exact destination and passes image-signature validation.

## Locate the bridge

Resolve the directory containing this loaded `SKILL.md`, then use its script by absolute path:

```sh
CODEX_IMAGEGEN_BRIDGE="/absolute/path/to/openai-imagegen/scripts/codex_imagegen.py"
python3 "$CODEX_IMAGEGEN_BRIDGE" --help
```

## Workflow

1. Decide whether the task is a new generation, an edit, or a JSONL batch.
2. Collect the prompt, exact output path, intended use, constraints, and any input-image roles.
3. Read [references/prompting.md](references/prompting.md), preserving specific user instructions and repeating edit invariants.
4. Run the appropriate bridge command from [references/cli.md](references/cli.md). Keep the output inside the current project workspace.
5. The bridge launches an ephemeral `codex exec` session, explicitly invokes System `$imagegen`, and attaches reference or edit images with Codex `--image` arguments.
6. Inspect the resulting image. If it misses a requirement, retry with one focused prompt change and repeat invariants.
7. Report the exact saved path and state that Codex System `imagegen` was used through the current Codex login.

Use `--force` only when the user explicitly authorized replacement. For multiple distinct images, use one batch job per image rather than asking one image-generation call to create a sprite sheet unless the user requested one.
