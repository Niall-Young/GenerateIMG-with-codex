#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "openai==3.6.0",
# ]
# ///
"""Generate and edit images with the official OpenAI GPT Image 2 API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import tempfile
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

MODEL = "gpt-image-2"
DEFAULT_SIZE = "auto"
DEFAULT_QUALITY = "medium"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_OUTPUT = "output/imagegen/output.png"
MAX_IMAGE_BYTES = 50 * 1024 * 1024
MAX_INPUT_IMAGES = 16
MAX_BATCH_JOBS = 500
ALLOWED_QUALITIES = {"low", "medium", "high", "auto"}
ALLOWED_FORMATS = {"png", "jpeg", "webp"}
MIN_PIXELS = 655_360
MAX_PIXELS = 8_294_400
MAX_EDGE = 3840
MAX_RATIO = 3.0


class CliError(RuntimeError):
    """Expected input, API, or output error shown without a traceback."""


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


def _validate_size(size: str) -> None:
    if size == "auto":
        return
    match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", size)
    if not match:
        raise CliError("--size must be auto or WIDTHxHEIGHT, for example 1024x1024.")
    width, height = int(match.group(1)), int(match.group(2))
    if width % 16 or height % 16:
        raise CliError("GPT Image 2 width and height must be multiples of 16.")
    if max(width, height) > MAX_EDGE:
        raise CliError("GPT Image 2 maximum edge is 3840 pixels.")
    if max(width, height) / min(width, height) > MAX_RATIO:
        raise CliError("GPT Image 2 aspect ratio must not exceed 3:1.")
    pixels = width * height
    if not MIN_PIXELS <= pixels <= MAX_PIXELS:
        raise CliError(
            "GPT Image 2 total pixels must be between 655,360 and 8,294,400."
        )


def _validate_common(*, size: str, quality: str, output_format: str, n: int) -> None:
    _validate_size(size)
    if quality not in ALLOWED_QUALITIES:
        raise CliError("--quality must be low, medium, high, or auto.")
    if output_format not in ALLOWED_FORMATS:
        raise CliError("--output-format must be png, jpeg, or webp.")
    if not 1 <= n <= 10:
        raise CliError("--n must be between 1 and 10.")


def _validate_images(raw_paths: Iterable[str]) -> list[Path]:
    paths = [Path(raw) for raw in raw_paths]
    if not paths:
        raise CliError("At least one --image is required for edit.")
    if len(paths) > MAX_INPUT_IMAGES:
        raise CliError(f"At most {MAX_INPUT_IMAGES} input images are supported.")
    for path in paths:
        if not path.is_file():
            raise CliError(f"Input image not found: {path}")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise CliError(f"Input image exceeds 50 MB: {path}")
    return paths


def _output_paths(out: str, output_format: str, n: int) -> list[Path]:
    path = Path(out)
    if path.suffix == "":
        path = path.with_suffix(f".{output_format}")
    expected_suffix = ".jpg" if output_format == "jpeg" else f".{output_format}"
    if path.suffix.lower() not in (
        {".jpg", ".jpeg"} if output_format == "jpeg" else {expected_suffix}
    ):
        raise CliError(
            f"Output extension {path.suffix} does not match --output-format {output_format}."
        )
    if n == 1:
        return [path]
    return [
        path.with_name(f"{path.stem}-{index}{path.suffix}") for index in range(1, n + 1)
    ]


def _ensure_outputs_available(paths: Iterable[Path], force: bool) -> None:
    if force:
        return
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise CliError(
            f"Output already exists: {', '.join(existing)} (use --force to replace)"
        )


def _extract_images(response: Any, expected: int) -> list[bytes]:
    data = getattr(response, "data", None)
    if not data:
        raise CliError("OpenAI returned no image data.")
    images: list[bytes] = []
    for item in data:
        encoded = getattr(item, "b64_json", None)
        if not encoded and isinstance(item, dict):
            encoded = item.get("b64_json")
        if not encoded:
            raise CliError("OpenAI response did not contain b64_json image data.")
        try:
            images.append(base64.b64decode(encoded, validate=True))
        except Exception as exc:
            raise CliError("OpenAI returned invalid base64 image data.") from exc
    if len(images) != expected:
        raise CliError(f"OpenAI returned {len(images)} image(s); expected {expected}.")
    return images


def _write_atomic(path: Path, content: bytes, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        if force:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise CliError(
                    f"Output already exists: {path} (use --force to replace)"
                ) from exc
            temporary.unlink()
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _write_outputs(
    images: Sequence[bytes], paths: Sequence[Path], force: bool
) -> list[str]:
    written: list[str] = []
    for image, path in zip(images, paths):
        _write_atomic(path, image, force)
        written.append(str(path))
    return written


def _client() -> Any:
    if not os.environ.get("OPENAI_API_KEY"):
        raise CliError(
            "OPENAI_API_KEY is not set. Export it before making a real request."
        )
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise CliError(
            "The OpenAI SDK is unavailable. Run this script with uv run --script."
        ) from exc
    return OpenAI()


def _generate(
    client: Any,
    *,
    prompt: str,
    out: str,
    size: str,
    quality: str,
    output_format: str,
    n: int,
    force: bool,
) -> dict[str, Any]:
    _validate_common(size=size, quality=quality, output_format=output_format, n=n)
    outputs = _output_paths(out, output_format, n)
    _ensure_outputs_available(outputs, force)
    response = client.images.generate(
        model=MODEL,
        prompt=prompt,
        size=size,
        quality=quality,
        output_format=output_format,
        n=n,
    )
    images = _extract_images(response, n)
    return {
        "status": "ok",
        "mode": "generate",
        "model": MODEL,
        "outputs": _write_outputs(images, outputs, force),
    }


def _edit(
    client: Any,
    *,
    image_paths: Sequence[Path],
    prompt: str,
    out: str,
    size: str,
    quality: str,
    output_format: str,
    n: int,
    force: bool,
) -> dict[str, Any]:
    _validate_common(size=size, quality=quality, output_format=output_format, n=n)
    outputs = _output_paths(out, output_format, n)
    _ensure_outputs_available(outputs, force)
    handles = [path.open("rb") for path in image_paths]
    try:
        response = client.images.edit(
            model=MODEL,
            image=handles,
            prompt=prompt,
            size=size,
            quality=quality,
            output_format=output_format,
            n=n,
        )
    finally:
        for handle in handles:
            handle.close()
    images = _extract_images(response, n)
    return {
        "status": "ok",
        "mode": "edit",
        "model": MODEL,
        "outputs": _write_outputs(images, outputs, force),
    }


def _plan(mode: str, **payload: Any) -> dict[str, Any]:
    return {"status": "dry-run", "mode": mode, "model": MODEL, "request": payload}


def _safe_batch_output(out_dir: Path, raw: str, output_format: str, n: int) -> str:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise CliError("Batch job out must be a relative path inside --out-dir.")
    root = out_dir.resolve()
    resolved = (out_dir / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise CliError("Batch job out escapes --out-dir.")
    _output_paths(str(resolved), output_format, n)
    return str(resolved)


def _load_batch(path: Path, out_dir: Path) -> list[dict[str, Any]]:
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
        prompt = str(value.get("prompt", "")).strip()
        if not prompt:
            raise CliError(f"Batch line {line_number} requires a non-empty prompt.")
        output_format = str(value.get("output_format", DEFAULT_OUTPUT_FORMAT)).lower()
        n = int(value.get("n", 1))
        size = str(value.get("size", DEFAULT_SIZE))
        quality = str(value.get("quality", DEFAULT_QUALITY))
        _validate_common(size=size, quality=quality, output_format=output_format, n=n)
        raw_out = str(value.get("out", f"image-{line_number}.{output_format}"))
        out = _safe_batch_output(out_dir, raw_out, output_format, n)
        jobs.append(
            {
                "line": line_number,
                "prompt": prompt,
                "out": out,
                "size": size,
                "quality": quality,
                "output_format": output_format,
                "n": n,
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
    concurrency: int,
    force: bool,
    client_factory: Callable[[], Any],
) -> dict[str, Any]:
    _validate_concurrency(concurrency)
    results: list[dict[str, Any]] = []

    def run(job: dict[str, Any]) -> dict[str, Any]:
        line = job["line"]
        kwargs = {key: value for key, value in job.items() if key != "line"}
        try:
            result = _generate(client_factory(), force=force, **kwargs)
            return {"line": line, **result}
        except Exception as exc:  # noqa: BLE001 - isolate each independent batch job
            return {"line": line, "status": "error", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {executor.submit(run, job): job["line"] for job in jobs}
        for future in as_completed(future_map):
            results.append(future.result())
    results.sort(key=lambda item: item["line"])
    failures = [item for item in results if item["status"] == "error"]
    return {
        "status": "partial" if failures else "ok",
        "mode": "generate-batch",
        "model": MODEL,
        "succeeded": len(results) - len(failures),
        "failed": len(failures),
        "results": results,
    }


def _validate_concurrency(concurrency: int) -> None:
    if concurrency < 1 or concurrency > 20:
        raise CliError("--concurrency must be between 1 and 20.")


def _add_prompt_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt")
    group.add_argument("--prompt-file")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", default=DEFAULT_OUTPUT)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument(
        "--quality", default=DEFAULT_QUALITY, choices=sorted(ALLOWED_QUALITIES)
    )
    parser.add_argument(
        "--output-format",
        default=DEFAULT_OUTPUT_FORMAT,
        choices=sorted(ALLOWED_FORMATS),
    )
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate", help="Generate one prompt or its variants."
    )
    _add_prompt_args(generate)
    _add_common_args(generate)

    edit = subparsers.add_parser("edit", help="Edit one or more images.")
    _add_prompt_args(edit)
    edit.add_argument("--image", action="append", required=True)
    _add_common_args(edit)

    batch = subparsers.add_parser(
        "generate-batch", help="Generate distinct jobs from JSONL."
    )
    batch.add_argument("--input", required=True)
    batch.add_argument("--out-dir", required=True)
    batch.add_argument("--concurrency", type=int, default=3)
    batch.add_argument("--force", action="store_true")
    batch.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "generate":
            prompt = _read_prompt(args.prompt, args.prompt_file)
            _validate_common(
                size=args.size,
                quality=args.quality,
                output_format=args.output_format,
                n=args.n,
            )
            outputs = [
                str(path)
                for path in _output_paths(args.out, args.output_format, args.n)
            ]
            _ensure_outputs_available((Path(path) for path in outputs), args.force)
            if args.dry_run:
                result = _plan(
                    "generate",
                    prompt=prompt,
                    size=args.size,
                    quality=args.quality,
                    output_format=args.output_format,
                    n=args.n,
                    outputs=outputs,
                )
            else:
                result = _generate(
                    _client(),
                    prompt=prompt,
                    out=args.out,
                    size=args.size,
                    quality=args.quality,
                    output_format=args.output_format,
                    n=args.n,
                    force=args.force,
                )
        elif args.command == "edit":
            prompt = _read_prompt(args.prompt, args.prompt_file)
            images = _validate_images(args.image)
            _validate_common(
                size=args.size,
                quality=args.quality,
                output_format=args.output_format,
                n=args.n,
            )
            outputs = [
                str(path)
                for path in _output_paths(args.out, args.output_format, args.n)
            ]
            _ensure_outputs_available((Path(path) for path in outputs), args.force)
            if args.dry_run:
                result = _plan(
                    "edit",
                    prompt=prompt,
                    images=[str(path) for path in images],
                    size=args.size,
                    quality=args.quality,
                    output_format=args.output_format,
                    n=args.n,
                    outputs=outputs,
                )
            else:
                result = _edit(
                    _client(),
                    image_paths=images,
                    prompt=prompt,
                    out=args.out,
                    size=args.size,
                    quality=args.quality,
                    output_format=args.output_format,
                    n=args.n,
                    force=args.force,
                )
        else:
            jobs = _load_batch(Path(args.input), Path(args.out_dir))
            _validate_concurrency(args.concurrency)
            if args.dry_run:
                result = _plan(
                    "generate-batch", concurrency=args.concurrency, jobs=jobs
                )
            else:
                result = _run_batch(
                    jobs,
                    concurrency=args.concurrency,
                    force=args.force,
                    client_factory=_client,
                )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get("status") == "partial" else 0
    except CliError as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False),
            file=os.sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns concise API errors
        print(
            json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False),
            file=os.sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
