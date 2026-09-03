using System.Collections.Concurrent;
using System.Threading.Channels;
using Microsoft.Extensions.Logging;

namespace TrainSwarm.Coordinator.Application.Commands;

public class TrainerConnectionManager(ILogger<TrainerConnectionManager> logger) : ITrainerConnectionManager
{
    private readonly ConcurrentDictionary<string, TrainerConnection> _connections = new();

    public TrainerConnection RegisterConnection(string trainerId, CancellationToken cancellationToken)
    {
        var channel = Channel.CreateUnbounded<CommandEnvelope>(new UnboundedChannelOptions
        {
            SingleReader = true,
            SingleWriter = false
        });

        var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        var newConnection = new TrainerConnection(trainerId, channel, linkedCts);

        _connections.AddOrUpdate(
            trainerId,
            addValueFactory: _ =>
            {
                logger.LogInformation("[TrainerConnectionManager] Trainer '{TrainerId}' registered active command stream.", trainerId);
                return newConnection;
            },
            updateValueFactory: (_, oldConnection) =>
            {
                logger.LogWarning("[TrainerConnectionManager] Trainer '{TrainerId}' reconnected. Superseding existing connection.", trainerId);
                try
                {
                    oldConnection.Channel.Writer.TryComplete();
                    oldConnection.CancellationTokenSource.Cancel();
                    oldConnection.CancellationTokenSource.Dispose();
                }
                catch (Exception ex)
                {
                    logger.LogDebug(ex, "[TrainerConnectionManager] Error disposing superseded connection for '{TrainerId}'.", trainerId);
                }
                return newConnection;
            });

        return newConnection;
    }

    public bool TryGetConnection(string trainerId, out TrainerConnection connection)
    {
        return _connections.TryGetValue(trainerId, out connection);
    }

    public bool RemoveConnection(string trainerId, TrainerConnection connection)
    {
        if (_connections.TryGetValue(trainerId, out var existing) && ReferenceEquals(existing, connection))
        {
            if (_connections.TryRemove(trainerId, out _))
            {
                logger.LogInformation("[TrainerConnectionManager] Trainer '{TrainerId}' connection closed and removed.", trainerId);
                try
                {
                    connection.Channel.Writer.TryComplete();
                    connection.CancellationTokenSource.Cancel();
                    connection.CancellationTokenSource.Dispose();
                }
                catch (Exception ex)
                {
                    logger.LogDebug(ex, "[TrainerConnectionManager] Error cleaning up removed connection for '{TrainerId}'.", trainerId);
                }
                return true;
            }
        }
        return false;
    }

    public bool IsConnected(string trainerId)
    {
        return _connections.ContainsKey(trainerId);
    }
}
