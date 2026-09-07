using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Application.Services;

public class ConnectTrainerDto
{
    public string TrainerNodeId { get; set; } = string.Empty;
    public TrainerStatus? Status { get; set; }
}
