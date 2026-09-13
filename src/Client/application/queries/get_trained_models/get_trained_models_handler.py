"""Handler for GetTrainedModelsQuery."""

from typing import List, Optional

try:
    from Client.infrastructure.persistence.model_repository import IModelRepository
except ImportError:
    from infrastructure.persistence.model_repository import IModelRepository

from .get_trained_models_query import GetTrainedModelsQuery, TrainedModelViewDto


class GetTrainedModelsQueryHandler:
    """Handles GetTrainedModelsQuery by reading trained model entities from persistence."""

    def __init__(self, model_repository: IModelRepository) -> None:
        self.model_repository = model_repository

    def handle(self, query: Optional[GetTrainedModelsQuery] = None) -> List[TrainedModelViewDto]:
        """Execute query returning all model versions recorded in persistence."""
        models = self.model_repository.get_all()

        results: List[TrainedModelViewDto] = []
        for m in models:
            if query and query.model_id and m.model_id != query.model_id:
                continue

            results.append(
                TrainedModelViewDto(
                    model_id=m.model_id,
                    model_version=str(m.model_version),
                    model_type=m.model_type,
                    dataset_id=m.dataset_id,
                    model_artifact_path=m.model_artifact_path,
                    training_config_path=m.training_config_path,
                )
            )
        return results
