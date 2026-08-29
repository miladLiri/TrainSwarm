using Grpc.Core;
using TrainSwarm.Coordinator.Domain.Commands;
using TrainSwarm.Coordinator.Grpc;
using ProtoEnvelope = TrainSwarm.Coordinator.Grpc.CommandEnvelope;

namespace TrainSwarm.Coordinator.Api.Grpc;

public class CoordinatorCommandServiceImpl(
    ITrainerConnectionManager connectionManager,
    ILogger<CoordinatorCommandServiceImpl> logger)
    : TrainSwarm.Coordinator.Grpc.CoordinatorCommandService.CoordinatorCommandServiceBase
{
    public override async Task SubscribeCommands(
        TrainerRegistrationRequest request,
        IServerStreamWriter<ProtoEnvelope> responseStream,
        ServerCallContext context)
    {
        var trainerId = request.TrainerId?.Trim();
        if (string.IsNullOrWhiteSpace(trainerId))
        {
            logger.LogWarning("[CoordinatorCommandService] Registration rejected: trainer_id is required.");
            throw new RpcException(new Status(StatusCode.InvalidArgument, "trainer_id must not be empty."));
        }

        var connection = connectionManager.RegisterConnection(trainerId, context.CancellationToken);
        logger.LogInformation("[CoordinatorCommandService] Established command stream for trainer '{TrainerId}'.", trainerId);

        try
        {
            while (await connection.Channel.Reader.WaitToReadAsync(connection.CancellationTokenSource.Token))
            {
                while (connection.Channel.Reader.TryRead(out var domainEnvelope))
                {
                    var protoEnvelope = new ProtoEnvelope
                    {
                        Id = domainEnvelope.Id,
                        Type = domainEnvelope.Type,
                        Data = domainEnvelope.Data
                    };

                    await responseStream.WriteAsync(protoEnvelope, connection.CancellationTokenSource.Token);
                    logger.LogInformation("[CoordinatorCommandService] Sent command '{CommandType}' (ID: '{CommandId}') over stream to trainer '{TrainerId}'.",
                        protoEnvelope.Type, protoEnvelope.Id, trainerId);
                }
            }
        }
        catch (OperationCanceledException)
        {
            logger.LogInformation("[CoordinatorCommandService] Command stream cancelled/disconnected for trainer '{TrainerId}'.", trainerId);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "[CoordinatorCommandService] Error on command stream for trainer '{TrainerId}'.", trainerId);
        }
        finally
        {
            connectionManager.RemoveConnection(trainerId, connection);
            logger.LogInformation("[CoordinatorCommandService] Closed command stream for trainer '{TrainerId}'.", trainerId);
        }
    }
}
