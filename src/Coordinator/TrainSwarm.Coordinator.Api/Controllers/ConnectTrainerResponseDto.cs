namespace TrainSwarm.Coordinator.Api.Controllers;

public class ConnectTrainerResponseDto
{
    public string Id { get; set; } = string.Empty;
    public string TrainerNodeId { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
}
