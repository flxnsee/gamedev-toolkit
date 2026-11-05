---
name: game-feel
description: Adds "juice" and responsive controls to a game - coyote time, jump buffering, variable jump height, hit stop, trauma-based screen shake, frame-rate independent smoothing, squash and stretch, audio variation. Use when the user says the game feels floaty, stiff, unresponsive, boring or "not juicy", asks to improve platformer or combat feel, or wants screen shake, hit pause, tweening or camera smoothing. Gives engine-agnostic rules plus Godot (GDScript) and Unity (C#) code; Unreal notes included.
license: MIT
metadata:
  author: gamedev-doctor
  version: "0.1.0"
---

# Game feel

Game feel is mostly forgiveness on input plus exaggerated feedback on output.
Work in this order, because each step is cheap and the earlier ones matter more:

1. **Input forgiveness**: coyote time, jump buffer, variable jump height.
2. **Feedback on impact**: hit stop, screen shake, flash, particles, sound.
3. **Motion polish**: easing, squash and stretch, camera smoothing.

Change one thing at a time and let the user play-test between changes. Expose every
number as a tunable (`@export` in Godot, `[SerializeField]` in Unity, `UPROPERTY(EditAnywhere)`
in Unreal) so the user can tweak without touching code.

## Starting values

| Technique | Typical value | Notes |
| --- | --- | --- |
| Coyote time | 0.08-0.15 s | Jump still allowed after walking off a ledge |
| Jump buffer | 0.1-0.15 s | Jump pressed slightly before landing still fires |
| Jump cut | multiply upward velocity by 0.4-0.5 on release | Gives variable height |
| Fall gravity | 1.5-2.5x rise gravity | Removes the "floaty" arc |
| Hit stop | 0.03-0.1 s (light-heavy hits) | Freeze the hitter and the target, not the UI |
| Shake | trauma 0-1, offset = max_offset * trauma^2 | Squaring makes small hits subtle |
| Pitch variation | random 0.9-1.1 | Stops repeated sounds feeling robotic |

## Frame-rate independent smoothing

`position = lerp(position, target, 0.1)` every frame is wrong: it moves faster at higher
frame rates. Use exponential decay instead:

```text
t = 1 - exp(-sharpness * delta)     # sharpness ~ 5 (lazy) .. 20 (snappy)
value = lerp(value, target, t)
```

## Godot 4 (GDScript): platformer controller core

```gdscript
extends CharacterBody2D

@export var speed := 220.0
@export var jump_velocity := -420.0
@export var gravity := 1200.0
@export var fall_gravity_mult := 1.8
@export var coyote_time := 0.1
@export var jump_buffer_time := 0.12
@export var jump_cut := 0.45

var _coyote := 0.0
var _buffer := 0.0

func _physics_process(delta: float) -> void:
	_coyote = coyote_time if is_on_floor() else maxf(_coyote - delta, 0.0)
	_buffer = jump_buffer_time if Input.is_action_just_pressed("jump") else maxf(_buffer - delta, 0.0)

	var g := gravity * (fall_gravity_mult if velocity.y > 0.0 else 1.0)
	velocity.y += g * delta

	if _buffer > 0.0 and _coyote > 0.0:
		velocity.y = jump_velocity
		_buffer = 0.0
		_coyote = 0.0
	if Input.is_action_just_released("jump") and velocity.y < 0.0:
		velocity.y *= jump_cut

	velocity.x = Input.get_axis("move_left", "move_right") * speed
	move_and_slide()
```

## Godot 4: trauma screen shake on a Camera2D

```gdscript
extends Camera2D

@export var max_offset := Vector2(12, 8)
@export var max_roll := 0.05
@export var decay := 1.5          # trauma lost per second
@export var noise: FastNoiseLite = FastNoiseLite.new()

var trauma := 0.0
var _t := 0.0

func add_trauma(amount: float) -> void:
	trauma = minf(trauma + amount, 1.0)

func _process(delta: float) -> void:
	_t += delta * 60.0
	trauma = maxf(trauma - decay * delta, 0.0)
	var s := trauma * trauma
	offset = Vector2(max_offset.x * s * noise.get_noise_2d(_t, 0.0),
		max_offset.y * s * noise.get_noise_2d(0.0, _t))
	rotation = max_roll * s * noise.get_noise_2d(_t, _t)
```

Noise instead of `randf()` gives smooth shake rather than jitter. Camera2D ignores its
own rotation by default: set `ignore_rotation = false` if you use roll.

## Godot 4: hit stop

```gdscript
func hit_stop(duration: float) -> void:
	Engine.time_scale = 0.0
	# process_always = true, ignore time scale = true: the timer still runs while paused
	await get_tree().create_timer(duration, true, false, true).timeout
	Engine.time_scale = 1.0
```

If several hits overlap, keep the longest remaining stop instead of stacking awaits.

## Unity (C#): hit stop and smoothing

```csharp
using System.Collections;
using UnityEngine;

public class HitStop : MonoBehaviour
{
    Coroutine _running;

    public void Stop(float duration)
    {
        if (_running != null) StopCoroutine(_running);
        _running = StartCoroutine(Run(duration));
    }

    IEnumerator Run(float duration)
    {
        Time.timeScale = 0f;
        yield return new WaitForSecondsRealtime(duration); // unaffected by timeScale
        Time.timeScale = 1f;
        _running = null;
    }
}

// Frame-rate independent follow:
// transform.position = Vector3.Lerp(transform.position, target.position,
//     1f - Mathf.Exp(-sharpness * Time.deltaTime));
```

For shake in Unity, prefer Cinemachine's Impulse system (Cinemachine Impulse Source +
Impulse Listener) over hand-rolled code. It already does trauma-style decay.

## Unreal notes

- Hit stop: `UGameplayStatics::SetGlobalTimeDilation(this, 0.01f)` and restore with a
  timer that uses real time, or use `CustomTimeDilation` on just the two actors involved.
- Shake: create a `UCameraShakeBase` Blueprint (Perlin noise pattern) and play it with
  `PlayerController->ClientStartCameraShake(ShakeClass, Scale)`.
- Coyote time: `ACharacter` already has `JumpMaxHoldTime` (variable height); coyote time is
  done by overriding `CanJumpInternal_Implementation` and checking time since
  `OnMovementModeChanged` left walking.

## Feedback checklist for every impact

- [ ] Hit stop on both attacker and target
- [ ] Target flashes white for 1-2 frames (shader parameter or modulate)
- [ ] Knockback in the hit direction
- [ ] Particles at the contact point
- [ ] Sound with pitch variation, layered (impact + material)
- [ ] Small screen shake scaled by damage
- [ ] Controller rumble if a gamepad is connected

Too much juice hurts readability. Offer a "reduce screen shake" accessibility option
whenever you add shake or flashes.
