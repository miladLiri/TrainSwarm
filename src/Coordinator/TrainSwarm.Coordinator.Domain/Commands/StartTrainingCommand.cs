using System.Text.Json.Serialization;

namespace TrainSwarm.Coordinator.Domain.Commands;

public class StartTrainingCommand
{
    [JsonPropertyName("trainingClientNodeId")]
    public required string TrainingClientNodeId { get; init; }

    [JsonPropertyName("sessionId")]
    public required string SessionId { get; init; }
}
