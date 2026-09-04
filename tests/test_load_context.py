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

    def test_multiple_patterns_combine_and_deduplicate_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "src").mkdir()
            (root / "docs" / "guide.md").write_text("GUIDE", encoding="utf-8")
            (root / "src" / "lib.rs").write_text("RUST", encoding="utf-8")
            (root / "ignored.txt").write_text("IGNORED", encoding="utf-8")

            output = self.run_hook("$context-file **/*.rs docs/*.md docs/guide.md", root)
            context = output["hookSpecificOutput"]["additionalContext"]

            self.assertEqual(context.count("GUIDE"), 1)
            self.assertEqual(context.count("RUST"), 1)
            self.assertLess(context.index("guide.md"), context.index("lib.rs"))
            self.assertNotIn("IGNORED", context)

    def test_quoted_patterns_support_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "design notes").mkdir()
            (root / "design notes" / "guide.md").write_text("GUIDE", encoding="utf-8")
            (root / "lib.rs").write_text("RUST", encoding="utf-8")

            output = self.run_hook(
                '$context-file:context-file "design notes/*.md" *.rs', root
            )
            context = output["hookSpecificOutput"]["additionalContext"]

            self.assertIn("GUIDE", context)
            self.assertIn("RUST", context)

    def test_unclosed_quote_blocks_turn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = self.run_hook('$context-file "docs/*.md', Path(directory))

            self.assertEqual(output["decision"], "block")
            self.assertIn("Invalid context patterns", output["reason"])

    def test_unrelated_prompt_has_no_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(self.run_hook("ordinary prompt", Path(directory)))

    def test_gitignore_filters_without_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text("*.rs\n!keep.rs\nbuild/\n", encoding="utf-8")
            (root / "keep.rs").write_text("KEEP", encoding="utf-8")
            (root / "skip.rs").write_text("SKIP", encoding="utf-8")
            (root / "build").mkdir()
            (root / "build" / ".gitignore").write_text("!keep.rs\n", encoding="utf-8")
            (root / "build" / "keep.rs").write_bytes(b"\xff")

            output = self.run_hook("$context-file **/*.rs keep.rs", root)
            context = output["hookSpecificOutput"]["additionalContext"]

            self.assertEqual(context.count("KEEP"), 1)
            self.assertNotIn("SKIP", context)
            self.assertNotIn("build", context)

    def test_nested_gitignore_overrides_parent_from_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "docs"
            nested.mkdir()
            (root / ".gitignore").write_text("*.md\n", encoding="utf-8")
            (nested / ".gitignore").write_text("!keep.md\n/local.txt\n", encoding="utf-8")
            (nested / "keep.md").write_text("KEEP", encoding="utf-8")
            (nested / "skip.md").write_text("SKIP", encoding="utf-8")
            (nested / "local.txt").write_text("LOCAL", encoding="utf-8")
            (nested / "sub").mkdir()
            (nested / "sub" / "local.txt").write_text("NESTED", encoding="utf-8")

            output = self.run_hook("$context-file **/*.*", nested)
            context = output["hookSpecificOutput"]["additionalContext"]

            self.assertIn("KEEP", context)
            self.assertIn("NESTED", context)
            self.assertNotIn("SKIP", context)
            self.assertNotIn("LOCAL", context)

    def test_explicit_ignored_file_blocks_turn(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text("skip.md\n", encoding="utf-8")
            (root / "skip.md").write_text("SKIP", encoding="utf-8")

            output = self.run_hook("$context-file skip.md", root)

            self.assertEqual(output["decision"], "block")
            self.assertIn("after .gitignore filtering", output["reason"])

    def test_tracked_files_filtered_but_git_excludes_not_used(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            (root / "tracked.md").write_text("TRACKED", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "tracked.md"], check=True)
            (root / ".gitignore").write_text("tracked.md\n", encoding="utf-8")
            (root / ".git" / "info" / "exclude").write_text("keep.md\n", encoding="utf-8")
            (root / "keep.md").write_text("KEEP", encoding="utf-8")

            output = self.run_hook("$context-file *.md", root)
            context = output["hookSpecificOutput"]["additionalContext"]

            self.assertIn("KEEP", context)
            self.assertNotIn("TRACKED", context)

    def test_repository_boundary_stops_parent_ignore_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text("*.md\n", encoding="utf-8")
            repository = root / "repo"
            subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
            (repository / "keep.md").write_text("KEEP", encoding="utf-8")

            output = self.run_hook("$context-file *.md", repository)

            self.assertIn("KEEP", output["hookSpecificOutput"]["additionalContext"])

    def test_absolute_and_parent_paths_use_their_own_ignore_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitignore").write_text("skip.md\n", encoding="utf-8")
            (root / "skip.md").write_text("SKIP", encoding="utf-8")
            (root / "keep.md").write_text("KEEP", encoding="utf-8")
            nested = root / "nested"
            nested.mkdir()

            output = self.run_hook(f'$context-file ../*.md "{root}/*.md"', nested)
            context = output["hookSpecificOutput"]["additionalContext"]

            self.assertEqual(context.count("KEEP"), 1)
            self.assertNotIn("SKIP", context)


if __name__ == "__main__":
    unittest.main()
