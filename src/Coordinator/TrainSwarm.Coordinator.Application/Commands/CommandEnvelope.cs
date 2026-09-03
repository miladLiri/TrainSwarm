namespace TrainSwarm.Coordinator.Application.Commands;

public class CommandEnvelope
{
    public required string Id { get; init; }
    public required string Type { get; init; }
    public required string Data { get; init; }
}
