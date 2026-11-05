#pragma once

#include "CoreMinimal.h"
#include "EnemyBase.generated.h"
#include "GameFramework/Actor.h"

UCLASS()
class MYGAME_API AEnemyBase : public AActor
{
	GENERATED_BODY()

public:
	AEnemyBase();

	UPROPERTY(EditAnywhere)
	TObjectPtr<UStaticMeshComponent> Mesh;

	AActor* Target;            // not visible to GC

	UPROPERTY()
	UMaterialInstanceDynamic* FlashMaterial;

	static AEnemyBase* Instance;
	void SetTarget(AActor* NewTarget);
};

USTRUCT(BlueprintType)
struct FEnemyStats
{
	float Health = 100.f;
};
