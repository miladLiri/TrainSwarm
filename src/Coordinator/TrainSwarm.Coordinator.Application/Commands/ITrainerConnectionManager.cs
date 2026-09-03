using System.Threading.Channels;

namespace TrainSwarm.Coordinator.Application.Commands;

public class TrainerConnection(string trainerId, Channel<CommandEnvelope> channel, CancellationTokenSource cancellationTokenSource)
{
    public string TrainerId { get; } = trainerId;
    public DateTime ConnectedAt { get; } = DateTime.UtcNow;
    public Channel<CommandEnvelope> Channel { get; } = channel;
    public CancellationTokenSource CancellationTokenSource { get; } = cancellationTokenSource;
}

public interface ITrainerConnectionManager
{
    TrainerConnection RegisterConnection(string trainerId, CancellationToken cancellationToken);
    bool TryGetConnection(string trainerId, out TrainerConnection connection);
    bool RemoveConnection(string trainerId, TrainerConnection connection);
    bool IsConnected(string trainerId);
}
