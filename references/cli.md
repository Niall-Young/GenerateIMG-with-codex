# Codex bridge CLI

Resolve the script relative to the loaded Skill:

```sh
CODEX_IMAGEGEN_BRIDGE="/absolute/path/to/openai-imagegen/scripts/codex_imagegen.py"
```

Prerequisites:

```sh
codex --version
codex login status
```

The login status must succeed. No `OPENAI_API_KEY` is used.

## Generate

```sh
python3 "$CODEX_IMAGEGEN_BRIDGE" generate \
  --prompt "A quiet editorial photograph of a ceramic cup at dawn, square composition" \
  --out output/imagegen/cup.png
```

Optional reference images may be repeated:

```sh
python3 "$CODEX_IMAGEGEN_BRIDGE" generate \
  --reference references/style.png \
  --prompt "Create a new harbor illustration using image 1 only as a style reference" \
  --out output/imagegen/harbor.png
```

## Edit

The first `--image` is the edit target. Additional images are supporting or reference inputs.

```sh
python3 "$CODEX_IMAGEGEN_BRIDGE" edit \
  --image input/product.png \
  --prompt "Replace only the background with warm gray; keep the product, label, proportions, and camera angle unchanged" \
  --out output/imagegen/product-edited.png
```

## Batch

Use one JSON object per line:

```json
{"mode":"generate","prompt":"A matte black teapot on stone","out":"teapot.png"}
{"mode":"edit","prompt":"Change only the background","out":"edited.png","images":["input/product.png"]}
```

Run the jobs through separate ephemeral Codex sessions:

```sh
python3 "$CODEX_IMAGEGEN_BRIDGE" generate-batch \
  --input prompts.jsonl \
  --out-dir output/imagegen/batch \
  --concurrency 2
```

Batch `out` values must be relative to `--out-dir`. Successful jobs remain available if another job fails.

## Shared behavior

- `--workspace`: project root passed to `codex exec`; defaults to the current directory.
- `--timeout`: maximum seconds per Codex run, default 900.
- `--force`: authorize replacement of an existing exact destination.
- `--dry-run`: print the instruction that would be sent to Codex without launching it.

The bridge uses `codex exec --ephemeral --sandbox workspace-write`. It validates that the output remains inside the workspace and that the final file has a PNG, JPEG, or WebP signature.
