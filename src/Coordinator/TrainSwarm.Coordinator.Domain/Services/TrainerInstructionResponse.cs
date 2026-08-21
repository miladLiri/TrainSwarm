namespace TrainSwarm.Coordinator.Domain.Services;

public class TrainerInstructionResponse
{
    public Guid TrainerId { get; set; }
    public bool IsCanceled { get; set; }
    public string? ClientNodeId { get; set; }
}