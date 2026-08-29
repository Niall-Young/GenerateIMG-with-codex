---
name: openai-imagegen
description: Generate or edit raster images through the official OpenAI GPT Image 2 API. Use when the user asks for image generation, image editing, visual variants, or batch image creation and the Agent does not have an equivalent built-in image-generation tool. Requires uv, network access, and OPENAI_API_KEY. Do not use for SVG or other deterministic code-native graphics.
metadata:
  version: "1.0.0"
  provider: "OpenAI"
  model: "gpt-image-2"
---

# OpenAI Image Generation

Generate and edit bitmap assets with the bundled deterministic CLI. The CLI uses only the official OpenAI API and always selects `gpt-image-2`.

Requires `uv`, network access, Python 3.10+, and an `OPENAI_API_KEY` with GPT Image API access.

## Boundaries

- Use this Skill for photos, illustrations, textures, product images, raster mockups, edits, and image variants.
- Prefer SVG, HTML/CSS, canvas, or the project's native source format for deterministic diagrams, icons, logos, and code-native graphics.
- Never expose, print, persist, or place `OPENAI_API_KEY` in a command. The CLI reads it from the process environment.
- Do not add a custom API base URL, proxy endpoint, or fallback model.
- Do not claim success until every requested output exists and can be decoded as an image.
- A real request costs money. For vague requests, clarify only details that materially affect the result; otherwise proceed with a sensible prompt.

## Locate the CLI

Resolve the directory containing this loaded `SKILL.md`, then use its bundled script by absolute path. Do not assume the current project contains the Skill.

```sh
OPENAI_IMAGEGEN_SCRIPT="/absolute/path/to/openai-imagegen/scripts/openai_imagegen.py"
uv run --script "$OPENAI_IMAGEGEN_SCRIPT" --help
```

If `uv`, network access, or `OPENAI_API_KEY` is unavailable, report the missing requirement instead of creating a replacement client.

## Choose a mode

- New image from text or reference-free variants: `generate`.
- Change an existing image while preserving requested invariants: `edit`.
- Many distinct prompts: `generate-batch` with JSONL. Use `--n` only for variants of the same prompt.

Read [references/cli.md](references/cli.md) for exact commands and JSONL fields. Read [references/prompting.md](references/prompting.md) before composing prompts or editing an image.

## Workflow

1. Determine whether the output is a new generation, an edit, or a batch.
2. Collect the prompt, intended use, exact visible text, constraints, output location, and input-image roles.
3. Shape the prompt with the minimum useful detail from `references/prompting.md`. For edits, repeat what must remain unchanged.
4. Choose an explicit output path in the user's project. Use `output/imagegen/` when the project has no established asset directory.
5. Run the CLI. Do not use `--force` unless the user explicitly requested replacement.
6. Inspect each output for subject, composition, text accuracy, edit invariants, and unwanted artifacts. Iterate with one targeted prompt change when necessary.
7. Report the final file paths, prompt or prompt set, size, quality, and that the official `gpt-image-2` API was used.

For a dry run that validates inputs without API use, add `--dry-run`. Dry runs do not create images and must never be presented as completed generation.
