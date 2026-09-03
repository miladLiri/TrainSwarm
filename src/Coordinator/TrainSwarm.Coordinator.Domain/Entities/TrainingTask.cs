using System;

namespace TrainSwarm.Coordinator.Domain.Entities;

public class TrainingTask
{
    public Guid TrainingTaskId { get; set; }
    public string ClientNodeId { get; set; }
    public string ModelId { get; set; }
    public string ModelVersion { get; set; }
    public string DataSetId { get; set; }
    public string ShardId { get; set; }
    public string TrainerNodeId { get; set; } = string.Empty;
}
