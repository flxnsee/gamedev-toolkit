#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GoodActor.generated.h"

UCLASS()
class MYGAME_API AGoodActor : public AActor
{
	GENERATED_BODY()
	UPROPERTY(VisibleAnywhere)
	TObjectPtr<USceneComponent> Root;
};
