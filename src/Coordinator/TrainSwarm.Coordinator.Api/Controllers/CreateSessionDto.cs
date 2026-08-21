namespace TrainSwarm.Coordinator.Api.Controllers;

public record CreateSessionDto(string ClientNodeId, string? Name = null);

