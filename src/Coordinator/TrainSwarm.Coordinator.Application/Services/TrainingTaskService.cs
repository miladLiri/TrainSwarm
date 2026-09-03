using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using ErrorOr;
using Microsoft.Extensions.Logging;
using TrainSwarm.Coordinator.Application.Contracts;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Application.Services;

public class TrainingTaskService
{
    private readonly ICoordinatorDbContext _dbContext;
    private readonly ILogger<TrainingTaskService> _logger;

    public TrainingTaskService(ICoordinatorDbContext dbContext, ILogger<TrainingTaskService> logger)
    {
        _dbContext = dbContext;
        _logger = logger;
    }

    public async Task<ErrorOr<CreateTrainingTaskResult>> CreateTrainingTaskAsync(
        CreateTrainingTaskDto request,
        CancellationToken ct = default)
    {
        if (request == null)
        {
            return Error.Validation("Invalid.Request", "Request body cannot be null.");
        }

        var validationErrors = ValidateRequest(request);
        if (validationErrors.Count > 0)
        {
            _logger.LogWarning("TrainingTask validation failed with {Count} errors for ClientNodeId={ClientNodeId}",
                validationErrors.Count, request.ClientNodeId);
            return validationErrors;
        }

        var tasks = new List<TrainingTask>();
        foreach (var shardId in request.ShardIdList)
        {
            tasks.Add(new TrainingTask
            {
                TrainingTaskId = Guid.NewGuid(),
                ClientNodeId = request.ClientNodeId,
                ModelId = request.ModelId,
                ModelVersion = request.ModelVersion,
                DataSetId = request.DataSetId,
                ShardId = shardId,
                TrainerNodeId = string.Empty
            });
        }

        try
        {
            await _dbContext.TrainingTasks.AddRangeAsync(tasks, ct);
            await _dbContext.SaveChangesAsync(ct);

            _logger.LogInformation(
                "Successfully created {ShardCount} training tasks: ClientNodeId={ClientNodeId}, ModelId={ModelId}, ModelVersion={ModelVersion}, DataSetId={DataSetId}",
                tasks.Count, request.ClientNodeId, request.ModelId, request.ModelVersion, request.DataSetId);

            return new CreateTrainingTaskResult(tasks.Select(t => t.TrainingTaskId));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex,
                "Failed to persist training tasks: ClientNodeId={ClientNodeId}, ModelId={ModelId}, ModelVersion={ModelVersion}, DataSetId={DataSetId}",
                request.ClientNodeId, request.ModelId, request.ModelVersion, request.DataSetId);
            throw;
        }
    }

    private static List<Error> ValidateRequest(CreateTrainingTaskDto request)
    {
        var errors = new List<Error>();

        if (string.IsNullOrWhiteSpace(request.ClientNodeId))
        {
            errors.Add(Error.Validation("Invalid.ClientNodeId", "ClientNodeId is required and cannot be empty or whitespace."));
        }

        if (string.IsNullOrWhiteSpace(request.ModelId))
        {
            errors.Add(Error.Validation("Invalid.ModelId", "ModelId is required and cannot be empty or whitespace."));
        }

        if (string.IsNullOrWhiteSpace(request.ModelVersion))
        {
            errors.Add(Error.Validation("Invalid.ModelVersion", "ModelVersion is required and cannot be empty or whitespace."));
        }

        if (string.IsNullOrWhiteSpace(request.DataSetId))
        {
            errors.Add(Error.Validation("Invalid.DataSetId", "DataSetId is required and cannot be empty or whitespace."));
        }

        if (request.ShardIdList == null || request.ShardIdList.Count == 0)
        {
            errors.Add(Error.Validation("Invalid.ShardIdList", "ShardIdList is required and must contain at least one shard ID."));
        }
        else
        {
            var seenShards = new HashSet<string>(StringComparer.Ordinal);
            bool hasDuplicate = false;

            foreach (var shard in request.ShardIdList)
            {
                if (string.IsNullOrWhiteSpace(shard))
                {
                    errors.Add(Error.Validation("Invalid.ShardId", "ShardId elements cannot be null, empty, or whitespace."));
                    break;
                }

                if (!seenShards.Add(shard))
                {
                    hasDuplicate = true;
                }
            }

            if (hasDuplicate)
            {
                errors.Add(Error.Validation("Invalid.DuplicateShardId", "ShardIdList cannot contain duplicate shard IDs."));
            }
        }

        return errors;
    }
}
