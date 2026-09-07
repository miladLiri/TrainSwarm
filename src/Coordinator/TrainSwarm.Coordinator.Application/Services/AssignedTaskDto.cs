using System;

namespace TrainSwarm.Coordinator.Application.Services;

public class AssignedTaskDto
{
    public Guid TrainingTaskId { get; set; }
    public string ModelId { get; set; } = string.Empty;
    public string TrainerNodeId { get; set; } = string.Empty;
    public string ShardId { get; set; } = string.Empty;
    public DateTime SubmitTime { get; set; }
}
