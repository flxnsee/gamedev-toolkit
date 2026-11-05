"""Builds a deliberately broken .blend for the Blender smoke test.
blender -b --factory-startup --python make_scene.py -- out.blend
"""
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)

bpy.ops.mesh.primitive_cube_add(size=2)
crate = bpy.context.object
crate.name = "Crate"
crate.scale = (2, 1, 1)                      # unapplied_scale

bpy.ops.mesh.primitive_cylinder_add(vertices=12)
pillar = bpy.context.object
pillar.name = "Pillar.001"                   # dup_name
pillar.scale = (-1, 1, 1)                    # negative_scale; caps are 12-gons -> ngons
while pillar.data.uv_layers:
    pillar.data.uv_layers.remove(pillar.data.uv_layers[0])  # no_uv

bpy.ops.object.armature_add()
bpy.context.object.name = "Armature"         # armature_name

img = bpy.data.images.new("ghost", 4, 4)
img.source = "FILE"
img.filepath = "//textures/missing.png"      # missing_texture
img.use_fake_user = True

bpy.ops.wm.save_as_mainfile(filepath=out)
