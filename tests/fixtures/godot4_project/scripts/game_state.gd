extends Node

@export var lives: int = 3
@onready var hud: Control = $HUD
var score := 0:
	set(value):
		score = maxi(value, 0)

func _ready() -> void:
	$Button.pressed.connect(_on_pressed)
	var tween := create_tween()
	var scene := preload("res://scenes/main.tscn").instantiate()
	await get_tree().create_timer(1.0).timeout
	print(randf_range(0, 1), deg_to_rad(90))
	var body: CharacterBody3D
	var area: Area3D

func _on_pressed() -> void:
	pass
