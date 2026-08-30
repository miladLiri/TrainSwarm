namespace TrainSwarm.Coordinator.Domain.Commands;

public record CommandDispatchResult(
    bool IsSuccess,
    string CommandId,
    string? FailureReason = null
)
{
    public static CommandDispatchResult Success(string commandId) =>
        new(true, commandId);

    public static CommandDispatchResult Failed(string commandId, string failureReason) =>
        new(false, commandId, failureReason);
}
