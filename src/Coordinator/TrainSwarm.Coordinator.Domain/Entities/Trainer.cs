using System;

namespace TrainSwarm.Coordinator.Domain.Entities;

public class Trainer
{
    public Guid Id { get; set; }
    public string TrainerNodeId { get; set; } = string.Empty;
    public TrainerStatus Status { get; set; } = TrainerStatus.IDLE;
}
