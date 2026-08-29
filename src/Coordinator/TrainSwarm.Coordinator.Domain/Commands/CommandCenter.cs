using System.Text.Json;
using Microsoft.Extensions.Logging;

namespace TrainSwarm.Coordinator.Domain.Commands;

public class CommandCenter(
    ITrainerConnectionManager connectionManager,
    ILogger<CommandCenter> logger) : ICommandCenter
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = false
    };

    public Task<CommandDispatchResult> SendAsync(string trainerId, CommandType type, object commandData)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(trainerId);
        ArgumentNullException.ThrowIfNull(commandData);

        var commandId = Guid.NewGuid().ToString();
        var typeName = type.ToString();

        string jsonData;
        try
        {
            jsonData = JsonSerializer.Serialize(commandData, JsonOptions);
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "[CommandCenter] Serialization error for command '{CommandType}' with ID '{CommandId}'.", typeName, commandId);
            return Task.FromResult(CommandDispatchResult.Failed(commandId, $"Serialization error: {ex.Message}"));
        }

        var envelope = new CommandEnvelope
        {
            Id = commandId,
            Type = typeName,
            Data = jsonData
        };

        if (!connectionManager.TryGetConnection(trainerId, out var connection) || connection == null)
        {
            logger.LogWarning("[CommandCenter] Cannot send command '{CommandType}' (ID: '{CommandId}'). Trainer '{TrainerId}' is not connected.", typeName, commandId, trainerId);
            return Task.FromResult(CommandDispatchResult.Failed(commandId, $"Trainer '{trainerId}' is not connected."));
        }

        try
        {
            if (connection.Channel.Writer.TryWrite(envelope))
            {
                logger.LogInformation("[CommandCenter] Dispatched command '{CommandType}' (ID: '{CommandId}') to trainer '{TrainerId}'.", typeName, commandId, trainerId);
                return Task.FromResult(CommandDispatchResult.Success(commandId));
            }

            logger.LogError("[CommandCenter] Transport channel for trainer '{TrainerId}' is full or closed. Failed to send command '{CommandId}'.", trainerId, commandId);
            return Task.FromResult(CommandDispatchResult.Failed(commandId, $"Transport channel for trainer '{trainerId}' is closed or full."));
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "[CommandCenter] Transport error writing command '{CommandId}' to trainer '{TrainerId}'.", commandId, trainerId);
            return Task.FromResult(CommandDispatchResult.Failed(commandId, $"Transport write error: {ex.Message}"));
        }
    }

    public Task<CommandDispatchResult> SendAsync<T>(string trainerId, T command) where T : class
    {
        ArgumentNullException.ThrowIfNull(command);

        var commandTypeName = typeof(T).Name;
        if (commandTypeName.EndsWith("Command", StringComparison.OrdinalIgnoreCase))
        {
            commandTypeName = commandTypeName[..^7];
        }

        if (!Enum.TryParse<CommandType>(commandTypeName, ignoreCase: true, out var commandType))
        {
            throw new ArgumentException($"Unsupported command type '{typeof(T).Name}'.", nameof(command));
        }

        return SendAsync(trainerId, commandType, command);
    }
}
