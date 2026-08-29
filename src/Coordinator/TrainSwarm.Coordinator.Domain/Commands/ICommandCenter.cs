namespace TrainSwarm.Coordinator.Domain.Commands;

public interface ICommandCenter
{
    Task<CommandDispatchResult> SendAsync(string trainerId, CommandType type, object commandData);
    Task<CommandDispatchResult> SendAsync<T>(string trainerId, T command) where T : class;
}
