---
name: unreal-cpp-gameplay
description: Writes correct Unreal Engine 5 gameplay C++ that compiles the first time and doesn't crash - naming prefixes, UCLASS/UPROPERTY/UFUNCTION specifiers, TObjectPtr and garbage collection, CreateDefaultSubobject vs NewObject vs SpawnActor, Enhanced Input setup, Build.cs dependencies, Blueprint exposure, timers instead of Tick, replication basics, logging, and building from the command line. Use whenever writing or reviewing Unreal C++ (AActor, ACharacter, UActorComponent, UGameInstanceSubsystem, GAS-free gameplay code), fixing "unresolved external symbol" or UHT errors, or deciding between C++ and Blueprint.
license: MIT
metadata:
  author: gamedev-toolkit
  version: "0.1.0"
---

# Unreal C++ gameplay

## Naming (UHT enforces most of it)

| Prefix | For | Example |
| --- | --- | --- |
| `A` | Actors (`AActor` subclasses) | `AEnemyCharacter` |
| `U` | Other `UObject`s, components, subsystems | `UHealthComponent` |
| `F` | Structs and plain C++ types | `FDamageInfo` |
| `E` | Enums (`UENUM` as `enum class EState : uint8`) | `EWeaponType` |
| `I` / `U` | Interface (`IInteractable`) and its `UInterface` (`UInteractable`) | |
| `T` | Templates | `TArray`, `TMap`, `TSubclassOf` |
| `b` | Booleans | `bIsDead` |

## Class skeleton

```cpp
// HealthComponent.h
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "HealthComponent.generated.h"   // always the LAST include

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnHealthChanged, float, NewHealth, float, Delta);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnDied);

UCLASS(ClassGroup = (Gameplay), meta = (BlueprintSpawnableComponent))
class MYGAME_API UHealthComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UHealthComponent();

    UFUNCTION(BlueprintCallable, Category = "Health")
    void ApplyDamage(float Amount);

    UFUNCTION(BlueprintPure, Category = "Health")
    float GetHealth() const { return Health; }

    UPROPERTY(BlueprintAssignable, Category = "Health")
    FOnHealthChanged OnHealthChanged;

    UPROPERTY(BlueprintAssignable, Category = "Health")
    FOnDied OnDied;

protected:
    virtual void BeginPlay() override;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "Health", meta = (ClampMin = "1"))
    float MaxHealth = 100.f;

private:
    UPROPERTY(VisibleInstanceOnly, Category = "Health")
    float Health = 0.f;
};
```

```cpp
// HealthComponent.cpp
#include "HealthComponent.h"

UHealthComponent::UHealthComponent()
{
    PrimaryComponentTick.bCanEverTick = false;   // don't tick unless you need to
}

void UHealthComponent::BeginPlay()
{
    Super::BeginPlay();                          // always call Super
    Health = MaxHealth;
}

void UHealthComponent::ApplyDamage(float Amount)
{
    if (Amount <= 0.f || Health <= 0.f) return;
    const float Old = Health;
    Health = FMath::Clamp(Health - Amount, 0.f, MaxHealth);
    OnHealthChanged.Broadcast(Health, Health - Old);
    if (Health <= 0.f) OnDied.Broadcast();
}
```

`MYGAME_API` is the module's export macro: `<MODULENAME uppercase>_API`.

## Memory and object rules

1. **Every `UObject*` member is a `UPROPERTY()`**, written as `TObjectPtr<UFoo>` in UE5.
   Without it the garbage collector doesn't see the reference, frees the object, and you
   crash later. Non-owning references that may die: `TWeakObjectPtr<AActor>`.
2. **Creating objects:**
   - Components in the constructor: `CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"))`. Constructor only.
   - Actors at runtime: `GetWorld()->SpawnActor<AProjectile>(ProjectileClass, Transform, Params)`.
   - Other UObjects: `NewObject<UMyObject>(Outer)`. **Never `new`** for UObjects.
3. **Class references for spawning**: `UPROPERTY(EditDefaultsOnly) TSubclassOf<AProjectile> ProjectileClass;`,
   set in the Blueprint subclass. Don't hard-code asset paths with `ConstructorHelpers` unless needed.
4. **Big assets**: `TSoftObjectPtr<UTexture2D>` / `TSoftClassPtr<>` plus async load, so they
   are not loaded with the class.
5. **Check validity**: `IsValid(Actor)` (handles null and pending-kill), not just `!= nullptr`.
6. **Don't do gameplay in constructors**: there's no world yet. Use `BeginPlay` /
   `PostInitializeComponents`.

## Tick vs timers vs events

Disable tick by default (`PrimaryActorTick.bCanEverTick = false`). For periodic work:

```cpp
GetWorldTimerManager().SetTimer(RegenTimer, this, &AMyActor::Regen, 0.5f, /*bLoop*/ true);
// header: FTimerHandle RegenTimer;
```

React to events (overlaps, delegates, input) instead of polling in Tick.

## Enhanced Input (UE 5.1+ default)

`Build.cs`: add `"EnhancedInput"` to `PublicDependencyModuleNames`.

```cpp
// Header
UPROPERTY(EditDefaultsOnly, Category = "Input") TObjectPtr<UInputMappingContext> DefaultContext;
UPROPERTY(EditDefaultsOnly, Category = "Input") TObjectPtr<UInputAction> MoveAction;
void Move(const FInputActionValue& Value);

// .cpp
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"

void AMyCharacter::BeginPlay()
{
    Super::BeginPlay();
    if (const APlayerController* PC = Cast<APlayerController>(GetController()))
        if (auto* Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
            Subsystem->AddMappingContext(DefaultContext, 0);
}

void AMyCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    if (auto* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent))
        EIC->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AMyCharacter::Move);
}

void AMyCharacter::Move(const FInputActionValue& Value)
{
    const FVector2D Axis = Value.Get<FVector2D>();
    AddMovementInput(GetActorForwardVector(), Axis.Y);
    AddMovementInput(GetActorRightVector(), Axis.X);
}
```

## Linker errors = missing module

`unresolved external symbol` for an engine class means its module isn't in `Build.cs`.
Common ones: `EnhancedInput`, `UMG` (+ `Slate`, `SlateCore`), `AIModule`, `NavigationSystem`,
`Niagara`, `GameplayTasks`, `PhysicsCore`, `NetCore`. Find the module from the class's
header path in the engine source (`Runtime/<Module>/...`) or the API docs page ("Module:").

## Replication basics

```cpp
// Constructor: bReplicates = true;
UPROPERTY(ReplicatedUsing = OnRep_Health) float Health;
UFUNCTION() void OnRep_Health();

void AMyActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AMyActor, Health);   // #include "Net/UnrealNetwork.h"
}

UFUNCTION(Server, Reliable) void ServerFire(FVector_NetQuantize Target);  // implement ServerFire_Implementation
```

Change replicated state only on the server (`HasAuthority()`). Clients ask through Server RPCs.

## Logging and asserts

```cpp
DECLARE_LOG_CATEGORY_EXTERN(LogMyGame, Log, All);   // header
DEFINE_LOG_CATEGORY(LogMyGame);                     // one .cpp
UE_LOG(LogMyGame, Warning, TEXT("Hit %s for %.1f"), *GetNameSafe(Target), Damage);
ensureMsgf(Weapon, TEXT("No weapon"));   // logs + continues (once)
check(Ptr);                               // crashes in dev builds; for real invariants only
```

## Building and Live Coding

- Small `.cpp` changes: Live Coding (Ctrl+Alt+F11) while the editor is open.
- **Header changes that alter layout** (new `UPROPERTY`, new `UFUNCTION`, new class): close
  the editor and build, otherwise Blueprints can corrupt or the editor crashes.
- Command line (Windows): `"<UE>/Engine/Build/BatchFiles/Build.bat" <Project>Editor Win64 Development -Project="<path>.uproject" -WaitMutex`
- Package: `"<UE>/Engine/Build/BatchFiles/RunUAT.bat" BuildCookRun -project="<path>.uproject" -platform=Win64 -clientconfig=Shipping -build -cook -stage -pak -archive -archivedirectory="<out>"`

## C++ or Blueprint?

C++ for systems, base classes, anything performance-sensitive, or with lots of math and loops.
Blueprint subclasses for tuning values, assets, visual and timeline logic. Expose
`BlueprintCallable` functions and `BlueprintImplementableEvent` hooks so designers can extend
without touching C++.
