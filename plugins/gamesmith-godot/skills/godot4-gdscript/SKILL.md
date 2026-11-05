---
name: godot4-gdscript
description: Writes idiomatic, typed Godot 4 GDScript and avoids the Godot 3 patterns that AI models and old tutorials still produce. Covers static typing, @export/@onready, signals with callables, await, scene composition, autoloads, resources, input actions, CharacterBody2D/3D movement, and a Godot 3 to 4 migration table. Use whenever writing or reviewing GDScript, creating Godot scenes or nodes in code, or when Godot reports parse errors such as "Unexpected identifier", "Function yield not found" or "Identifier not declared".
license: MIT
metadata:
  author: gamesmith
  version: "0.1.0"
---

# Godot 4 GDScript

Most GDScript online is Godot 3, and models trained on it mix the two. **Before writing
code, check `project.godot`: `config_version=5` is Godot 4.** Then follow these rules.

## Rules

1. **Type everything.** Typed code is faster and catches errors in the editor.
   `var speed: float = 200.0`, `var enemies: Array[Enemy] = []`, `func hit(dmg: int) -> void:`.
   Use `:=` when the type is obvious: `var dir := Vector2.ZERO`.
2. **Annotations, not keywords**: `@export`, `@onready`, `@tool`, `@export_range(0, 100)`,
   `@export_group("Movement")`, `@icon("res://icon.svg")`, `class_name Player` at the top.
3. **Signals are objects**: declare `signal died(score: int)`, emit `died.emit(score)`,
   connect `player.died.connect(_on_player_died)`. Bind extra args with
   `_on_hit.bind(enemy)`. Prefer connecting in code or the editor, never by string.
4. **`await` replaces `yield`**: `await get_tree().create_timer(0.5).timeout`,
   `await anim.animation_finished`.
5. **Call down, signal up.** Parents call methods on children; children emit signals.
   Never `get_parent().get_parent()`. Use `%UniqueName` (scene-unique nodes) instead of
   long `$A/B/C` paths.
6. **Input via actions**, defined in Project Settings → Input Map:
   `Input.get_vector("left", "right", "up", "down")`, `Input.is_action_just_pressed("jump")`.
   Handle one-off events in `_unhandled_input(event)` so UI can consume clicks first.
7. **Physics in `_physics_process`**, visuals in `_process`. Multiply by `delta`.
8. **Data in Resources**: make `class_name WeaponData extends Resource` with `@export` fields
   and create `.tres` files, instead of dictionaries or JSON for game data.
9. **Autoloads sparingly**: for truly global services (save system, audio bus, event bus).
   Not for passing references between two nodes.
10. **Free nodes with `queue_free()`**, not `free()`, during gameplay.

## Movement templates

```gdscript
# 2D top-down
extends CharacterBody2D

@export var speed: float = 200.0

func _physics_process(_delta: float) -> void:
	velocity = Input.get_vector("left", "right", "up", "down") * speed
	move_and_slide()
```

```gdscript
# 3D character
extends CharacterBody3D

@export var speed: float = 5.0
@export var jump_velocity: float = 4.5
var gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")

func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= gravity * delta
	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = jump_velocity
	var input := Input.get_vector("left", "right", "forward", "back")
	var dir := (transform.basis * Vector3(input.x, 0, input.y)).normalized()
	velocity.x = dir.x * speed
	velocity.z = dir.z * speed
	move_and_slide()
```

## Spawning and tweens

```gdscript
const BULLET := preload("res://scenes/bullet.tscn")

func shoot() -> void:
	var b := BULLET.instantiate() as Bullet
	b.global_position = %Muzzle.global_position
	get_tree().current_scene.add_child(b)

func pop() -> void:
	var t := create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	t.tween_property(self, "scale", Vector2.ONE * 1.2, 0.08)
	t.tween_property(self, "scale", Vector2.ONE, 0.12)
```

## Godot 3 → 4 migration table

| Godot 3 | Godot 4 |
| --- | --- |
| `onready var x = $X` | `@onready var x: Node = $X` |
| `export var hp = 3` / `export(int) var` | `@export var hp: int = 3` |
| `tool` | `@tool` |
| `yield(obj, "sig")` | `await obj.sig` |
| `var x setget set_x, get_x` | `var x: int:` + `set(v):` / `get:` blocks, or `set = set_x` |
| `connect("pressed", self, "_on")` | `pressed.connect(_on)` |
| `emit_signal("hit", 1)` | `hit.emit(1)` (old form still works) |
| `move_and_slide(vel, Vector2.UP)` | set `velocity`, `up_direction`; call `move_and_slide()` |
| `KinematicBody2D` / `KinematicBody` | `CharacterBody2D` / `CharacterBody3D` |
| `Spatial` | `Node3D` |
| `Position2D` / `Position3D` | `Marker2D` / `Marker3D` |
| `scene.instance()` | `scene.instantiate()` |
| `get_tree().change_scene("res://x.tscn")` | `get_tree().change_scene_to_file("res://x.tscn")` |
| `Tween.new()` + `add_child` | `create_tween()` |
| `rect_position`, `rect_size`, `rect_min_size` | `position`, `size`, `custom_minimum_size` |
| `rand_range`, `deg2rad`, `stepify`, `range_lerp` | `randf_range`, `deg_to_rad`, `snapped`, `remap` |
| `File.new()` / `Directory.new()` | `FileAccess.open(path, FileAccess.READ)` / `DirAccess.open(path)` |
| `to_json` / `parse_json` | `JSON.stringify` / `JSON.parse_string` |
| `OS.get_ticks_msec()` | `Time.get_ticks_msec()` |
| `PoolStringArray`, `PoolVector2Array` | `PackedStringArray`, `PackedVector2Array` |
| `BUTTON_LEFT` | `MOUSE_BUTTON_LEFT` |
| `remote func` / `master func` | `@rpc("any_peer")` / `@rpc("authority")` |
| `.empty()` | `.is_empty()` |
| `funcref(obj, "m")` | `obj.m` (Callable) |
| `update()` on CanvasItem | `queue_redraw()` |

## After writing code

If the `godot-project-lint` skill is available, run it to catch remaining Godot 3 patterns
and broken `res://` paths. If Godot is installed, `godot --headless --path . --quit` reports
script parse errors without opening the editor.
