"""Handler for GetTrainingShardsQuery."""

from typing import List, Optional

try:
    from Client.infrastructure.persistence.training_shard_repository import ITrainingShardRepository
except ImportError:
    from infrastructure.persistence.training_shard_repository import ITrainingShardRepository

from .get_training_shards_query import GetTrainingShardsQuery, TrainingShardViewDto


class GetTrainingShardsQueryHandler:
    """Handles GetTrainingShardsQuery by reading training shard state from persistence."""

    def __init__(self, shard_repository: ITrainingShardRepository) -> None:
        self.shard_repository = shard_repository

    def handle(self, query: Optional[GetTrainingShardsQuery] = None) -> List[TrainingShardViewDto]:
        """Execute query returning a list of TrainingShardViewDto objects."""
        if query and query.model_id and query.model_version and query.dataset_id:
            shards = self.shard_repository.get_by_model_version_and_dataset(
                query.model_id, query.model_version, query.dataset_id
            )
        else:
            shards = self.shard_repository.get_all()

        results: List[TrainingShardViewDto] = []
        for s in shards:
            if query:
                if query.model_id and s.model_id != query.model_id:
                    continue
                if query.model_version and str(s.model_version) != str(query.model_version):
                    continue
                if query.dataset_id and s.dataset_id != query.dataset_id:
                    continue

            status_str = s.status.value if hasattr(s.status, "value") else str(s.status)
            results.append(
                TrainingShardViewDto(
                    model_id=s.model_id,
                    model_version=str(s.model_version),
                    dataset_id=s.dataset_id,
                    shard_id=s.shard_id,
                    status=status_str,
                    sample_count=s.sample_count,
                    trainer_node_id=s.trainer_node_id,
                    update_artifact_path=s.update_artifact_path,
                    metrics=s.metrics,
                )
            )
        return results
