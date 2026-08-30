from __future__ import annotations

import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "codex_imagegen.py"
SPEC = importlib.util.spec_from_file_location("codex_imagegen", SCRIPT)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image"


class ValidationTests(unittest.TestCase):
    def test_output_must_stay_in_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            with self.assertRaises(bridge.CliError):
                bridge._output_path("../escape.png", workspace)

    def test_edit_instruction_invokes_system_imagegen_and_locks_target(self):
        instruction = bridge._instruction(
            mode="edit",
            prompt="change only the background",
            output=Path("/tmp/result.png"),
            images=[Path("/tmp/input.png")],
            force=False,
        )
        self.assertIn("System $imagegen", instruction)
        self.assertIn("built-in image_gen tool", instruction)
        self.assertIn("edit target", instruction)
        self.assertIn("/tmp/result.png", instruction)

    def test_command_uses_ephemeral_logged_in_codex(self):
        command = bridge._command(
            codex="/usr/local/bin/codex",
            workspace=Path("/tmp/project"),
            instruction="generate",
            images=[Path("/tmp/reference.png")],
            last_message=Path("/tmp/last.txt"),
        )
        self.assertEqual(command[:2], ["/usr/local/bin/codex", "exec"])
        self.assertIn("--ephemeral", command)
        self.assertIn("workspace-write", command)
        self.assertIn("--image", command)
        self.assertNotIn("OPENAI_API_KEY", " ".join(command))

    def test_batch_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            source = workspace / "jobs.jsonl"
            source.write_text(
                json.dumps({"prompt": "test", "out": "../escape.png"}),
                encoding="utf-8",
            )
            with self.assertRaises(bridge.CliError):
                bridge._load_batch(source, workspace / "output", workspace)


class BridgeFlowTests(unittest.TestCase):
    @patch.object(bridge, "_codex_preflight", return_value="/usr/local/bin/codex")
    @patch.object(bridge.subprocess, "run")
    def test_real_mode_runs_codex_and_validates_output(self, run, _preflight):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            output = workspace / "result.png"

            def fake_run(command, **_kwargs):
                last_message = Path(command[command.index("--output-last-message") + 1])
                last_message.write_text(f"Saved to {output}", encoding="utf-8")
                output.write_bytes(PNG_BYTES)
                return types.SimpleNamespace(returncode=0, stdout="", stderr="")

            run.side_effect = fake_run
            result = bridge._run_one(
                mode="generate",
                prompt="test",
                output=output,
                workspace=workspace,
                images=[],
                timeout=60,
                force=False,
                dry_run=False,
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["backend"], "codex-system-imagegen")
            self.assertEqual(output.read_bytes(), PNG_BYTES)

    def test_dry_run_needs_no_codex_or_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            output = workspace / "result.png"
            with patch.object(bridge, "_codex_preflight") as preflight:
                result = bridge._run_one(
                    mode="generate",
                    prompt="test",
                    output=output,
                    workspace=workspace,
                    images=[],
                    timeout=60,
                    force=False,
                    dry_run=True,
                )
            preflight.assert_not_called()
            self.assertEqual(result["status"], "dry-run")
            self.assertFalse(output.exists())

    def test_invalid_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fake.png"
            output.write_bytes(b"not-an-image")
            with self.assertRaises(bridge.CliError):
                bridge._validate_image(output)


if __name__ == "__main__":
    unittest.main()
