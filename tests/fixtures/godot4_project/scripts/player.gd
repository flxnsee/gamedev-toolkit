extends KinematicBody2D

export var speed = 200
onready var sprite = $Sprite
var hp = 3 setget set_hp

# yield(get_tree(), "idle_frame")  <- comment, must not be reported
const DOC = "Spatial and yield( inside a string are fine"

func _ready():
	$Button.connect("pressed", self, "_on_pressed")
	var t = Tween.new()
	var e = preload("res://scenes/enemy.tscn").instance()
	var icon = load("res://Art/hero.png")

func _physics_process(delta):
	velocity = move_and_slide(velocity, Vector2.UP)
	yield(get_tree().create_timer(1.0), "timeout")
	print(rand_range(0, 1), deg2rad(90))
	$Label.rect_position = Vector2.ZERO
