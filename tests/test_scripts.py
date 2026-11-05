"""Tests for the deterministic gamedev-doctor scripts. Run: python -m unittest discover tests"""
from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures"


def load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


godot_lint = load("plugins/godot-doctor/skills/godot-project-lint/scripts/godot_lint.py", "godot_lint")
unity_check = load("plugins/unity-doctor/skills/unity-project-hygiene/scripts/unity_meta_check.py", "unity_check")
ue_check = load("plugins/unreal-doctor/skills/unreal-project-hygiene/scripts/ue_project_check.py", "ue_check")
gen_repo = load("plugins/gamedev-core/skills/game-repo-setup/scripts/gen_repo_files.py", "gen_repo")
validator = load("tools/validate_skills.py", "validator")


def codes(report, key="findings"):
    return [(f["code"], f.get("file") or f.get("path"), f.get("line")) for f in report[key]]


class GodotLintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = godot_lint.lint_project(FIX / "godot4_project")
        cls.found = codes(cls.rep)

    def has(self, code, file, line=None):
        return any(c == code and f == file and (line is None or l == line) for c, f, l in self.found)

    def test_detects_godot4(self):
        self.assertEqual(self.rep["godot_major"], 4)

    def test_godot3_syntax(self):
        for code, line in [("gd3-class", 1), ("gd3-export", 3), ("gd3-onready", 4), ("gd3-setget", 5),
                           ("gd3-connect", 11), ("gd3-tween-node", 12), ("gd3-instance", 13),
                           ("gd3-move-and-slide", 17), ("gd3-yield", 18), ("gd3-rect", 20)]:
            self.assertTrue(self.has(code, "scripts/player.gd", line), f"{code} at line {line}")

    def test_reports_every_renamed_function_on_a_line(self):
        funcs = [l for c, f, l in self.found if c == "gd3-func" and f == "scripts/player.gd"]
        self.assertEqual(funcs, [19, 19])

    def test_comments_and_strings_ignored(self):
        self.assertFalse(any(f == "scripts/player.gd" and l in (7, 8) for _, f, l in self.found))

    def test_clean_godot4_script_has_no_findings(self):
        self.assertFalse(any(f == "scripts/game_state.gd" for _, f, _ in self.found))

    def test_addons_skipped_by_default(self):
        self.assertFalse(any(f.startswith("addons/") for _, f, _ in self.found))
        rep = godot_lint.lint_project(FIX / "godot4_project", include_addons=True)
        self.assertTrue(any(f["file"].startswith("addons/") for f in rep["findings"]))

    def test_resource_paths(self):
        self.assertTrue(self.has("missing-resource", "project.godot"))
        self.assertTrue(self.has("missing-resource", "scenes/main.tscn", 6))
        self.assertTrue(self.has("missing-resource", "scripts/player.gd", 13))
        self.assertTrue(self.has("path-case", "scenes/main.tscn", 4))
        self.assertTrue(self.has("stale-path", "scenes/main.tscn", 5))
        # existing, correctly cased references are not reported
        self.assertFalse(self.has("missing-resource", "scenes/main.tscn", 3))
        self.assertFalse(any(f == "scripts/player.gd" and l == 14 for _, f, l in self.found))

    def test_cli_exit_codes(self):
        self.assertEqual(godot_lint.main([str(FIX / "godot4_project"), "--json"]), 1)
        self.assertEqual(godot_lint.main([str(FIX)]), 2)


class UnityCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = unity_check.check(FIX / "unity_project")
        cls.found = {(f["code"], f["path"]) for f in cls.rep["findings"]}

    def test_version(self):
        self.assertEqual(self.rep["unity_version"], "6000.2.10f1")

    def test_meta_problems(self):
        self.assertIn(("missing-meta", "Assets/Textures"), self.found)
        self.assertIn(("missing-meta", "Assets/Textures/hero.png"), self.found)
        self.assertIn(("orphan-meta", "Assets/Scripts/Deleted.cs.meta"), self.found)
        self.assertTrue(any(c == "duplicate-guid" for c, _ in self.found))

    def test_hidden_entries_ignored(self):
        self.assertFalse(any("Docs~" in p or ".DS_Store" in p for _, p in self.found))

    def test_serialization(self):
        self.assertIn(("binary-asset", "Assets/Scenes/Main.unity"), self.found)
        self.assertIn(("serialization-not-text", "ProjectSettings/EditorSettings.asset"), self.found)

    def test_not_unity(self):
        self.assertEqual(unity_check.main([str(FIX / "godot4_project")]), 2)


class UnrealCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = ue_check.check(FIX / "ue_project")
        cls.found = codes(cls.rep)

    def has(self, code, path=None, line=None):
        return any(c == code and (path is None or p == path) and (line is None or l == line) for c, p, l in self.found)

    def test_project_structure(self):
        self.assertEqual(self.rep["engine"], "5.6")
        self.assertTrue(self.has("module-missing"))
        self.assertTrue(self.has("no-editor-target"))
        self.assertTrue(self.has("plugin-unbuilt"))

    def test_header_lint(self):
        h = "Source/MyGame/Public/EnemyBase.h"
        self.assertTrue(self.has("generated-include-order", h, 4))
        self.assertTrue(self.has("missing-generated-body", h, 27))
        self.assertTrue(self.has("raw-uobject-member", h, 18))
        # UPROPERTY-marked raw pointer, static and function params are fine
        self.assertFalse(self.has("raw-uobject-member", h, 21))
        self.assertFalse(self.has("raw-uobject-member", h, 23))
        self.assertFalse(any(p == "Source/MyGame/Public/GoodActor.h" for _, p, _ in self.found))

    def test_git_setup(self):
        self.assertTrue(self.has("no-lfs"))
        self.assertTrue(self.has("gitignore-incomplete"))


class GenRepoFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_write_then_skip_then_merge(self):
        self.assertEqual(gen_repo.main(["--engine", "unreal", "--out", str(self.tmp)]), 0)
        ga = (self.tmp / ".gitattributes").read_text()
        self.assertIn("*.uasset filter=lfs diff=lfs merge=lfs -text lockable", ga)
        self.assertIn("Intermediate/", (self.tmp / ".gitignore").read_text())

        (self.tmp / ".gitignore").write_text("node_modules/\n")
        gen_repo.main(["--engine", "unity", "--out", str(self.tmp)])  # no flag: untouched
        self.assertEqual((self.tmp / ".gitignore").read_text(), "node_modules/\n")

        gen_repo.main(["--engine", "unity", "--out", str(self.tmp), "--merge"])
        merged = (self.tmp / ".gitignore").read_text()
        self.assertTrue(merged.startswith("node_modules/\n"))
        self.assertIn(gen_repo.MARKER, merged)
        self.assertIn("/[Ll]ibrary/", merged)

        before = (self.tmp / ".gitignore").read_text()
        gen_repo.main(["--engine", "unity", "--out", str(self.tmp), "--merge"])  # idempotent
        self.assertEqual((self.tmp / ".gitignore").read_text(), before)

    def test_godot_keeps_import_files(self):
        lines = gen_repo.build_gitignore(["godot"])
        self.assertIn(".godot/", lines)
        self.assertFalse(any("*.import" in l for l in lines))


class ValidatorTest(unittest.TestCase):
    def test_repo_is_valid(self):
        self.assertEqual(validator.main(), 0)

    def test_frontmatter_parser(self):
        fm, body, errs = validator.parse_frontmatter(
            "---\nname: a-b\ndescription: \"x\"\nmetadata:\n  version: \"1.0\"\n---\n# Body\n")
        self.assertEqual(errs, [])
        self.assertEqual(fm["metadata"], {"version": "1.0"})
        self.assertEqual(body.strip(), "# Body")


if __name__ == "__main__":
    unittest.main()
