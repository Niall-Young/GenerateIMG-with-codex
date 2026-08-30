#!/usr/bin/env python3
"""Bridge other coding agents to Codex's built-in imagegen capability."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 900
DEFAULT_CONCURRENCY = 2
MAX_BATCH_JOBS = 100
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class CliError(RuntimeError):
    """Expected bridge, Codex, or output error shown without a traceback."""


def _read_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt and prompt_file:
        raise CliError("Use --prompt or --prompt-file, not both.")
    if prompt_file:
        path = Path(prompt_file)
        if not path.is_file():
            raise CliError(f"Prompt file not found: {path}")
        value = path.read_text(encoding="utf-8").strip()
    else:
        value = (prompt or "").strip()
    if not value:
        raise CliError("A non-empty prompt is required.")
    return value


def _workspace(raw: str | None) -> Path:
    path = Path(raw).expanduser().resolve() if raw else Path.cwd().resolve()
    if not path.is_dir():
        raise CliError(f"Workspace directory not found: {path}")
    return path


def _output_path(raw: str, workspace: Path) -> Path:
    path = Path(raw).expanduser()
    path = path.resolve() if path.is_absolute() else (workspace / path).resolve()
    if path != workspace and workspace not in path.parents:
        raise CliError("Output must be inside --workspace.")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise CliError("Output must use .png, .jpg, .jpeg, or .webp.")
    return path


def _input_images(
    raw_paths: Sequence[str], workspace: Path | None = None
) -> list[Path]:
    images: list[Path] = []
    for raw in raw_paths:
        path = Path(raw).expanduser()
        if not path.is_absolute() and workspace is not None:
            path = workspace / path
        path = path.resolve()
        if not path.is_file():
            raise CliError(f"Input image not found: {path}")
        images.append(path)
    return images


def _file_digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_image(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise CliError(f"Codex did not create the requested image: {path}")
    with path.open("rb") as handle:
        header = handle.read(16)
    suffix = path.suffix.lower()
    valid = (
        suffix == ".png"
        and header.startswith(b"\x89PNG\r\n\x1a\n")
        or suffix in {".jpg", ".jpeg"}
        and header.startswith(b"\xff\xd8\xff")
        or suffix == ".webp"
        and header.startswith(b"RIFF")
        and header[8:12] == b"WEBP"
    )
    if not valid:
        raise CliError(f"Output is not a valid {suffix} image: {path}")


def _codex_preflight() -> str:
    executable = shutil.which("codex")
    if not executable:
        raise CliError("Codex CLI is not installed or is not available on PATH.")
    status = subprocess.run(
        [executable, "login", "status"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if status.returncode != 0:
        detail = (status.stderr or status.stdout).strip()
        raise CliError(f"Codex is not logged in. Run `codex login`. {detail}".strip())
    return executable


def _instruction(
    *, mode: str, prompt: str, output: Path, images: Sequence[Path], force: bool
) -> str:
    image_roles = ""
    if images:
        if mode == "edit":
            roles = ["edit target"] + ["supporting/reference input"] * (len(images) - 1)
        else:
            roles = ["visual reference"] * len(images)
        image_roles = "\n".join(
            f"- Attached image {index}: {role}; local source {path}"
            for index, (path, role) in enumerate(zip(images, roles), start=1)
        )

    mode_rule = (
        "Treat attached image 1 as the edit target. Preserve everything the request does not "
        "explicitly ask to change."
        if mode == "edit"
        else "Generate a new raster image. Attached images, if any, are references rather than edit targets."
    )
    overwrite_rule = (
        "The caller explicitly authorized replacement, so overwrite the exact destination if it exists."
        if force
        else "The destination does not exist. Do not choose a sibling or versioned filename."
    )
    return f"""Use the Codex System $imagegen skill and its built-in image_gen tool to complete this image task.

You must actually call the built-in image generation tool. Do not substitute Python drawing, SVG, HTML, CSS, canvas, placeholders, or prompt-only advice.

Mode: {mode}
User request:
{prompt}

{mode_rule}
{image_roles}

Save the selected final bitmap to this exact absolute path:
{output}

{overwrite_rule}
Before finishing, inspect the generated result and verify that the exact destination exists. Keep the final response concise and include the saved path."""


def _command(
    *,
    codex: str,
    workspace: Path,
    instruction: str,
    images: Sequence[Path],
    last_message: Path,
) -> list[str]:
    command = [
        codex,
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(workspace),
        "--output-last-message",
        str(last_message),
    ]
    for image in images:
        command.extend(["--image", str(image)])
    command.append(instruction)
    return command


def _run_one(
    *,
    mode: str,
    prompt: str,
    output: Path,
    workspace: Path,
    images: Sequence[Path],
    timeout: int,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    if timeout < 30 or timeout > 3600:
        raise CliError("--timeout must be between 30 and 3600 seconds.")
    previous_digest = _file_digest(output)
    if previous_digest and not force:
        raise CliError(f"Output already exists: {output} (use --force to replace)")

    instruction = _instruction(
        mode=mode, prompt=prompt, output=output, images=images, force=force
    )
    if dry_run:
        return {
            "status": "dry-run",
            "mode": mode,
            "backend": "codex-system-imagegen",
            "workspace": str(workspace),
            "output": str(output),
            "images": [str(path) for path in images],
            "instruction": instruction,
        }

    codex = _codex_preflight()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="codex-imagegen-") as temporary:
        last_message = Path(temporary) / "last-message.txt"
        command = _command(
            codex=codex,
            workspace=workspace,
            instruction=instruction,
            images=images,
            last_message=last_message,
        )
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise CliError(
                f"Codex image generation timed out after {timeout} seconds."
            ) from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise CliError(f"Codex image generation failed: {detail[-4000:]}")
        final_message = (
            last_message.read_text(encoding="utf-8").strip()
            if last_message.is_file()
            else ""
        )

    _validate_image(output)
    current_digest = _file_digest(output)
    if previous_digest and current_digest == previous_digest:
        raise CliError("Codex completed without replacing the existing output.")
    return {
        "status": "ok",
        "mode": mode,
        "backend": "codex-system-imagegen",
        "output": str(output),
        "bytes": output.stat().st_size,
        "codex_message": final_message,
    }


def _load_batch(path: Path, out_dir: Path, workspace: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CliError(f"Batch input not found: {path}")
    jobs: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CliError(f"Invalid JSON on line {line_number}: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise CliError(f"Batch line {line_number} must be a JSON object.")
        mode = str(value.get("mode", "generate"))
        if mode not in {"generate", "edit"}:
            raise CliError(f"Batch line {line_number} mode must be generate or edit.")
        prompt = str(value.get("prompt", "")).strip()
        if not prompt:
            raise CliError(f"Batch line {line_number} requires a non-empty prompt.")
        raw_out = str(value.get("out", f"image-{line_number}.png"))
        candidate = Path(raw_out)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise CliError(f"Batch line {line_number} out must stay inside --out-dir.")
        output = _output_path(str(out_dir / candidate), workspace)
        images = _input_images(
            [str(item) for item in value.get("images", [])], workspace
        )
        if mode == "edit" and not images:
            raise CliError(f"Batch line {line_number} edit requires images.")
        jobs.append(
            {
                "line": line_number,
                "mode": mode,
                "prompt": prompt,
                "output": output,
                "images": images,
            }
        )
    if not jobs:
        raise CliError("Batch input contains no jobs.")
    if len(jobs) > MAX_BATCH_JOBS:
        raise CliError(f"Batch input exceeds the {MAX_BATCH_JOBS}-job limit.")
    return jobs


def _run_batch(
    jobs: Sequence[dict[str, Any]],
    *,
    workspace: Path,
    concurrency: int,
    timeout: int,
    force: bool,
    dry_run: bool,
) -> dict[str, Any]:
    if concurrency < 1 or concurrency > 5:
        raise CliError("--concurrency must be between 1 and 5.")

    def run(job: dict[str, Any]) -> dict[str, Any]:
        line = job["line"]
        kwargs = {key: value for key, value in job.items() if key != "line"}
        try:
            result = _run_one(
                workspace=workspace,
                timeout=timeout,
                force=force,
                dry_run=dry_run,
                **kwargs,
            )
            return {"line": line, **result}
        except Exception as exc:  # noqa: BLE001 - isolate independent Codex runs
            return {"line": line, "status": "error", "error": str(exc)}

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(run, job) for job in jobs]
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["line"])
    failures = [item for item in results if item["status"] == "error"]
    return {
        "status": "partial" if failures else ("dry-run" if dry_run else "ok"),
        "backend": "codex-system-imagegen",
        "succeeded": len(results) - len(failures),
        "failed": len(failures),
        "results": results,
    }


def _add_prompt_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt")
    group.add_argument("--prompt-file")


def _add_shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", required=True)
    parser.add_argument("--workspace")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate", help="Generate through Codex imagegen."
    )
    _add_prompt_args(generate)
    generate.add_argument("--reference", action="append", default=[])
    _add_shared_args(generate)

    edit = subparsers.add_parser("edit", help="Edit through Codex imagegen.")
    _add_prompt_args(edit)
    edit.add_argument("--image", action="append", required=True)
    _add_shared_args(edit)

    batch = subparsers.add_parser(
        "generate-batch", help="Run JSONL jobs through Codex."
    )
    batch.add_argument("--input", required=True)
    batch.add_argument("--out-dir", required=True)
    batch.add_argument("--workspace")
    batch.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    batch.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    batch.add_argument("--force", action="store_true")
    batch.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = _workspace(args.workspace)
        if args.command in {"generate", "edit"}:
            prompt = _read_prompt(args.prompt, args.prompt_file)
            raw_images = args.reference if args.command == "generate" else args.image
            images = _input_images(raw_images, workspace)
            output = _output_path(args.out, workspace)
            result = _run_one(
                mode=args.command,
                prompt=prompt,
                output=output,
                workspace=workspace,
                images=images,
                timeout=args.timeout,
                force=args.force,
                dry_run=args.dry_run,
            )
        else:
            out_dir = Path(args.out_dir).expanduser()
            out_dir = out_dir if out_dir.is_absolute() else workspace / out_dir
            jobs = _load_batch(Path(args.input), out_dir.resolve(), workspace)
            result = _run_batch(
                jobs,
                workspace=workspace,
                concurrency=args.concurrency,
                timeout=args.timeout,
                force=args.force,
                dry_run=args.dry_run,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") == "partial" else 0
    except CliError as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns concise Codex errors
        print(
            json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
