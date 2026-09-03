import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).parents[1] / "plugins" / "context-file"
HOOKS = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text())
HOOK_COMMAND = HOOKS["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]


class LoadContextTest(unittest.TestCase):
    def run_hook(self, prompt: str, cwd: Path) -> dict | None:
        result = subprocess.run(
            HOOK_COMMAND.replace("${PLUGIN_ROOT}", str(PLUGIN_ROOT)),
            input=json.dumps({"prompt": prompt, "cwd": str(cwd)}),
            text=True,
            capture_output=True,
            check=True,
            shell=True,
        )
        return json.loads(result.stdout) if result.stdout else None

    def test_glob_loads_sorted_matching_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b.md").write_text("BETA", encoding="utf-8")
            (root / "a.md").write_text("ALPHA", encoding="utf-8")
            (root / "ignored.txt").write_text("IGNORED", encoding="utf-8")

            output = self.run_hook("$context-file *.md", root)
            context = output["hookSpecificOutput"]["additionalContext"]

            self.assertLess(context.index("a.md"), context.index("b.md"))
            self.assertIn("ALPHA", context)
            self.assertIn("BETA", context)
            self.assertNotIn("IGNORED", context)

    def test_namespaced_skill_invocation_loads_matching_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "context.md").write_text("NAMESPACED", encoding="utf-8")

            output = self.run_hook("$context-file:context-file *.md", root)

            self.assertIn(
                "NAMESPACED",
                output["hookSpecificOutput"]["additionalContext"],
            )

    def test_recursive_glob_loads_nested_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "docs" / "nested"
            nested.mkdir(parents=True)
            (nested / "file.md").write_text("NESTED", encoding="utf-8")

            output = self.run_hook("$context-file docs/**/*.md", root)

            self.assertIn(
                "NESTED",
                output["hookSpecificOutput"]["additionalContext"],
            )

    def test_no_match_blocks_turn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = self.run_hook("$context-file *.md", Path(directory))

            self.assertEqual(output["decision"], "block")
            self.assertIn("No files matched", output["reason"])

    def test_unrelated_prompt_has_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(self.run_hook("ordinary prompt", Path(directory)))


if __name__ == "__main__":
    unittest.main()
