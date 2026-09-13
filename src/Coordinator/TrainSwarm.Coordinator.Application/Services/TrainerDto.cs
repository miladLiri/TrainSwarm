using System;

namespace TrainSwarm.Coordinator.Application.Services;

public class TrainerDto
{
    public Guid Id { get; set; }
    public string TrainerNodeId { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
}

public class TrainingTaskDto
{
    public Guid TrainingTaskId { get; set; }
    public string ClientNodeId { get; set; } = string.Empty;
    public string ModelId { get; set; } = string.Empty;
    public string ModelVersion { get; set; } = string.Empty;
    public string DataSetId { get; set; } = string.Empty;
    public string ShardId { get; set; } = string.Empty;
    public string TrainerNodeId { get; set; } = string.Empty;
    public DateTime SubmitTime { get; set; }
}
