# CLI reference

Set the script path from the directory containing the loaded `SKILL.md`:

```sh
OPENAI_IMAGEGEN_SCRIPT="/absolute/path/to/openai-imagegen/scripts/openai_imagegen.py"
```

Every real command requires `OPENAI_API_KEY`. Dependencies are isolated by `uv` from the inline script metadata.

## Generate

```sh
uv run --script "$OPENAI_IMAGEGEN_SCRIPT" generate \
  --prompt "A quiet editorial photograph of a ceramic cup at dawn" \
  --size 1024x1024 \
  --quality low \
  --out output/imagegen/cup.png
```

Use `--prompt-file` instead of `--prompt` for long prompts. `--n 2` creates `cup-1.png` and `cup-2.png`. Defaults are `size=auto`, `quality=medium`, `output-format=png`, and `n=1`.

## Edit

```sh
uv run --script "$OPENAI_IMAGEGEN_SCRIPT" edit \
  --image input/product.png \
  --prompt "Replace only the background with warm gray; keep the product, label, proportions, and camera angle unchanged" \
  --out output/imagegen/product-edited.png
```

Repeat `--image` for multiple inputs and describe each image's index and role in the prompt. Up to 16 images are accepted. The CLI rejects missing inputs and warns through a clear error when an input exceeds the API's 50 MB limit.

## Batch generation

Create a JSONL file with one JSON object per distinct asset:

```json
{"prompt":"A matte black teapot on stone","out":"teapot.png","size":"1024x1024","quality":"low"}
{"prompt":"A folded linen napkin on oak","out":"napkin.png","size":"1024x1024","quality":"low"}
```

Then run:

```sh
uv run --script "$OPENAI_IMAGEGEN_SCRIPT" generate-batch \
  --input prompts.jsonl \
  --out-dir output/imagegen/batch \
  --concurrency 3
```

Per-job fields are `prompt`, `out`, `size`, `quality`, `n`, and `output_format`. `out` must be a relative filename within `--out-dir`; absolute paths and `..` traversal are rejected. Successful jobs remain available when another job fails, and the command exits nonzero with a JSON failure summary.

## Shared options

- `--size`: `auto` or a GPT Image 2 size whose edges are multiples of 16, maximum edge is 3840, aspect ratio is at most 3:1, and total pixels are between 655,360 and 8,294,400.
- `--quality`: `low`, `medium`, `high`, or `auto`.
- `--output-format`: `png`, `jpeg`, or `webp`.
- `--n`: 1 to 10 variants of one prompt.
- `--force`: explicitly allow replacing existing output files.
- `--dry-run`: validate and print the planned request without network access or file creation.

The CLI intentionally exposes no `--model`, `--base-url`, or transparent-background fallback. Unsupported requests must be explained instead of silently routed elsewhere.
