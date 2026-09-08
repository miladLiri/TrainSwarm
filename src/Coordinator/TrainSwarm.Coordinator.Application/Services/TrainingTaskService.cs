using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using ErrorOr;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using TrainSwarm.Coordinator.Application.Contracts;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Application.Services;

public class TrainingTaskService
{
    private readonly ICoordinatorDbContext _dbContext;
    private readonly ILogger<TrainingTaskService> _logger;
    private readonly ISchedulerCursorState _schedulerCursorState;
    private readonly IServiceScopeFactory _scopeFactory;
    private static readonly SemaphoreSlim _schedulingLock = new(1, 1);

    public TrainingTaskService(
        ICoordinatorDbContext dbContext,
        ILogger<TrainingTaskService> logger,
        ISchedulerCursorState schedulerCursorState,
        IServiceScopeFactory scopeFactory)
    {
        _dbContext = dbContext;
        _logger = logger;
        _schedulerCursorState = schedulerCursorState;
        _scopeFactory = scopeFactory;
    }

    public async Task<ErrorOr<Success>> ClearTasksAsync(CancellationToken ct = default)
    {
        try
        {
            var tasks = await _dbContext.TrainingTasks.ToListAsync(ct);
            if (tasks.Count > 0)
            {
                _dbContext.TrainingTasks.RemoveRange(tasks);
                await _dbContext.SaveChangesAsync(ct);
            }

            _schedulerCursorState.Reset();
            _logger.LogInformation("Successfully cleared {Count} training task(s) and reset scheduler cursor.", tasks.Count);
            return Result.Success;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to clear training tasks.");
            return Error.Failure("TrainingTasks.ClearFailed", "Failed to clear training tasks.");
        }
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
                TrainingTaskId = request.TrainingTaskId ?? Guid.NewGuid(),
                ClientNodeId = request.ClientNodeId,
                ModelId = request.ModelId,
                ModelVersion = request.ModelVersion,
                DataSetId = request.DataSetId,
                ShardId = shardId,
                TrainerNodeId = request.TrainerNodeId ?? string.Empty,
                SubmitTime = request.SubmitTime ?? DateTime.Now
            });
        }

        try
        {
            await _dbContext.TrainingTasks.AddRangeAsync(tasks, ct);
            await _dbContext.SaveChangesAsync(ct);

            _logger.LogInformation(
                "Successfully created {ShardCount} training tasks: ClientNodeId={ClientNodeId}, ModelId={ModelId}, ModelVersion={ModelVersion}, DataSetId={DataSetId}",
                tasks.Count, request.ClientNodeId, request.ModelId, request.ModelVersion, request.DataSetId);

            TriggerBackgroundScheduling();

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

    private void TriggerBackgroundScheduling()
    {
        _ = Task.Run(async () =>
        {
            try
            {
                await _schedulingLock.WaitAsync();
                try
                {
                    using var scope = _scopeFactory.CreateScope();
                    var scheduler = scope.ServiceProvider.GetRequiredService<SchedulerService>();
                    var logger = scope.ServiceProvider.GetRequiredService<ILogger<TrainingTaskService>>();

                    logger.LogInformation("[BackgroundScheduler] Starting background task assignment cycle...");
                    var result = await scheduler.AssignTasksAsync();
                    if (result.IsError)
                    {
                        logger.LogWarning("[BackgroundScheduler] Task assignment cycle ended with error: {Error}", result.FirstError.Description);
                    }
                    else
                    {
                        logger.LogInformation("[BackgroundScheduler] Task assignment cycle completed successfully: {Count} task(s) assigned.", result.Value.Count);
                    }
                }
                finally
                {
                    _schedulingLock.Release();
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "[BackgroundScheduler] Unhandled exception occurred during background task assignment.");
            }
        });
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
