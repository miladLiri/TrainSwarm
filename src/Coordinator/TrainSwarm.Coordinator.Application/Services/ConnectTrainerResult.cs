using System;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Application.Services;

public class ConnectTrainerResult
{
    public Guid Id { get; }
    public string TrainerNodeId { get; }
    public TrainerStatus Status { get; }

    public ConnectTrainerResult(Guid id, string trainerNodeId, TrainerStatus status)
    {
        Id = id;
        TrainerNodeId = trainerNodeId;
        Status = status;
    }
}
