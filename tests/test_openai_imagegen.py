from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "openai_imagegen.py"
SPEC = importlib.util.spec_from_file_location("openai_imagegen", SCRIPT)
assert SPEC and SPEC.loader
imagegen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(imagegen)


class FakeImages:
    def __init__(self, payload: bytes = b"image-bytes") -> None:
        self.payload = payload
        self.generate_calls: list[dict] = []
        self.edit_calls: list[dict] = []

    def _response(self, n: int):
        encoded = base64.b64encode(self.payload).decode("ascii")
        return types.SimpleNamespace(
            data=[types.SimpleNamespace(b64_json=encoded) for _ in range(n)]
        )

    def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        return self._response(kwargs["n"])

    def edit(self, **kwargs):
        self.edit_calls.append(kwargs)
        return self._response(kwargs["n"])


class FakeClient:
    def __init__(self, payload: bytes = b"image-bytes") -> None:
        self.images = FakeImages(payload)


class ValidationTests(unittest.TestCase):
    def test_accepts_supported_sizes(self):
        for size in ("auto", "1024x1024", "2048x1152", "3840x2160"):
            imagegen._validate_size(size)

    def test_rejects_invalid_size(self):
        with self.assertRaises(imagegen.CliError):
            imagegen._validate_size("1000x1000")

    def test_multiple_output_names(self):
        paths = imagegen._output_paths("result.png", "png", 2)
        self.assertEqual(paths, [Path("result-1.png"), Path("result-2.png")])

    def test_batch_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "jobs.jsonl"
            source.write_text(
                json.dumps({"prompt": "test", "out": "../escape.png"}), encoding="utf-8"
            )
            with self.assertRaises(imagegen.CliError):
                imagegen._load_batch(source, Path(directory) / "output")

    def test_batch_preserves_base_name_for_multiple_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "jobs.jsonl"
            source.write_text(
                json.dumps({"prompt": "test", "out": "result.png", "n": 2}),
                encoding="utf-8",
            )
            jobs = imagegen._load_batch(source, Path(directory) / "output")
            self.assertEqual(Path(jobs[0]["out"]).name, "result.png")
            self.assertEqual(
                [
                    path.name
                    for path in imagegen._output_paths(jobs[0]["out"], "png", 2)
                ],
                ["result-1.png", "result-2.png"],
            )

    def test_rejects_invalid_concurrency_even_for_dry_run(self):
        with self.assertRaises(imagegen.CliError):
            imagegen._validate_concurrency(0)


class ApiFlowTests(unittest.TestCase):
    def test_generate_decodes_and_writes_all_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient(b"valid-image")
            result = imagegen._generate(
                client,
                prompt="test prompt",
                out=str(Path(directory) / "result.png"),
                size="1024x1024",
                quality="low",
                output_format="png",
                n=2,
                force=False,
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(len(result["outputs"]), 2)
            for output in result["outputs"]:
                self.assertEqual(Path(output).read_bytes(), b"valid-image")
            self.assertEqual(client.images.generate_calls[0]["model"], "gpt-image-2")

    def test_generate_refuses_existing_output_before_api_call(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.png"
            output.write_bytes(b"original")
            client = FakeClient()
            with self.assertRaises(imagegen.CliError):
                imagegen._generate(
                    client,
                    prompt="test",
                    out=str(output),
                    size="auto",
                    quality="medium",
                    output_format="png",
                    n=1,
                    force=False,
                )
            self.assertEqual(client.images.generate_calls, [])
            self.assertEqual(output.read_bytes(), b"original")

    def test_edit_closes_inputs_and_writes_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            output = Path(directory) / "edited.png"
            source.write_bytes(b"source")
            client = FakeClient(b"edited")
            result = imagegen._edit(
                client,
                image_paths=[source],
                prompt="change only the background",
                out=str(output),
                size="auto",
                quality="medium",
                output_format="png",
                n=1,
                force=False,
            )
            self.assertEqual(result["mode"], "edit")
            self.assertEqual(output.read_bytes(), b"edited")
            self.assertTrue(client.images.edit_calls[0]["image"][0].closed)

    def test_batch_reports_partial_success(self):
        class FailingImages(FakeImages):
            def generate(self, **kwargs):
                if kwargs["prompt"] == "bad":
                    raise RuntimeError("simulated failure")
                return super().generate(**kwargs)

        class MixedClient:
            def __init__(self):
                self.images = FailingImages()

        with tempfile.TemporaryDirectory() as directory:
            jobs = [
                {
                    "line": 1,
                    "prompt": "good",
                    "out": str(Path(directory) / "good.png"),
                    "size": "auto",
                    "quality": "low",
                    "output_format": "png",
                    "n": 1,
                },
                {
                    "line": 2,
                    "prompt": "bad",
                    "out": str(Path(directory) / "bad.png"),
                    "size": "auto",
                    "quality": "low",
                    "output_format": "png",
                    "n": 1,
                },
            ]
            result = imagegen._run_batch(
                jobs, concurrency=2, force=False, client_factory=MixedClient
            )
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["succeeded"], 1)
            self.assertEqual(result["failed"], 1)
            self.assertTrue((Path(directory) / "good.png").exists())


if __name__ == "__main__":
    unittest.main()
