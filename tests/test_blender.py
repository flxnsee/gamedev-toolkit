"""Blender smoke test. Runs only when the BLENDER env var points at a Blender executable:
  BLENDER="/path/to/blender" python -m unittest tests.test_blender
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLENDER = os.environ.get("BLENDER")
AUDIT = ROOT / "plugins/blender-doctor/skills/blender-scene-audit/scripts/scene_audit.py"
EXPORT = ROOT / "plugins/blender-doctor/skills/blender-export-to-engine/scripts/export_for_engine.py"


def run_blender(*args: str) -> str:
    r = subprocess.run([BLENDER, "-b", "--factory-startup", *args], capture_output=True, text=True, timeout=300)
    return r.stdout + r.stderr


def between(text: str, begin: str, end: str) -> dict:
    return json.loads(text.split(begin, 1)[1].split(end, 1)[0])


@unittest.skipUnless(BLENDER, "set BLENDER=/path/to/blender to run")
class BlenderSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.blend = cls.tmp / "broken.blend"
        run_blender("--python", str(ROOT / "tests/blender/make_scene.py"), "--", str(cls.blend))
        assert cls.blend.exists(), "test scene was not created"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_audit_finds_planted_problems(self):
        out = run_blender(str(self.blend), "--python", str(AUDIT), "--", "--max-tris", "10")
        rep = between(out, "AUDIT_JSON_BEGIN", "AUDIT_JSON_END")
        by_obj = {o["name"]: {i["code"] for i in o["issues"]} for o in rep["objects"]}
        self.assertIn("unapplied_scale", by_obj["Crate"])
        self.assertTrue({"negative_scale", "no_uv", "ngons", "dup_name"} <= by_obj["Pillar.001"])
        self.assertIn("armature_name", by_obj["Armature"])
        self.assertIn("missing_texture", {i["code"] for i in rep["scene_issues"]})
        self.assertEqual(rep["totals"]["meshes"], 2)

    def test_export_every_engine(self):
        for engine in ("godot", "gltf", "unity", "unreal"):
            with self.subTest(engine=engine):
                target = self.tmp / "out" / f"model_{engine}"
                out = run_blender(str(self.blend), "--python", str(EXPORT), "--", "--engine", engine, "--out", str(target))
                rep = between(out, "EXPORT_JSON_BEGIN", "EXPORT_JSON_END")
                self.assertTrue(rep["ok"])
                self.assertGreater(rep["bytes"], 0)
                self.assertEqual(rep["skipped_options"], [])


if __name__ == "__main__":
    unittest.main()
