using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using ErrorOr;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using TrainSwarm.Coordinator.Application.Commands;
using TrainSwarm.Coordinator.Application.Contracts;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Application.Services;

public class SchedulerService
{
    private readonly ICoordinatorDbContext _dbContext;
    private readonly ISchedulerCursorState _cursorState;
    private readonly ICommandCenter _commandCenter;
    private readonly ILogger<SchedulerService> _logger;

    public SchedulerService(
        ICoordinatorDbContext dbContext,
        ISchedulerCursorState cursorState,
        ICommandCenter commandCenter,
        ILogger<SchedulerService> logger)
    {
        _dbContext = dbContext;
        _cursorState = cursorState;
        _commandCenter = commandCenter;
        _logger = logger;
    }

    public async Task<ErrorOr<List<AssignedTaskDto>>> AssignTasksAsync(CancellationToken ct = default)
    {
        try
        {
            // 1. Retrieve all eligible idle trainers (Status == IDLE), ordered deterministically by TrainerNodeId ASC
        var availableTrainers = await _dbContext.Trainers
            .Where(t => t.Status == TrainerStatus.IDLE)
            .OrderBy(t => t.TrainerNodeId)
            .ToListAsync(ct);

        if (availableTrainers.Count == 0)
        {
            _logger.LogInformation("No idle trainers available for scheduling.");
            return new List<AssignedTaskDto>();
        }

        // 2. Retrieve all unassigned tasks (string.IsNullOrEmpty(TrainerNodeId))
        var unassignedTasks = await _dbContext.TrainingTasks
            .Where(t => string.IsNullOrEmpty(t.TrainerNodeId))
            .OrderBy(t => t.SubmitTime)
            .ThenBy(t => t.TrainingTaskId)
            .ToListAsync(ct);

        if (unassignedTasks.Count == 0)
        {
            _logger.LogInformation("No unassigned tasks available for scheduling.");
            return new List<AssignedTaskDto>();
        }

        // 3. Group tasks into queues per ModelId (FIFO ordered by SubmitTime ASC, TrainingTaskId ASC)
        var modelQueues = new Dictionary<string, Queue<TrainingTask>>(StringComparer.Ordinal);
        foreach (var task in unassignedTasks)
        {
            if (!modelQueues.TryGetValue(task.ModelId, out var queue))
            {
                queue = new Queue<TrainingTask>();
                modelQueues[task.ModelId] = queue;
            }
            queue.Enqueue(task);
        }

        // Deterministic ordering of active models
        var activeModelIds = modelQueues.Keys
            .OrderBy(m => m, StringComparer.Ordinal)
            .ToList();

        // 4. Resolve starting cursor position
        var currentCursor = _cursorState.GetCurrentCursor();
        int currentIndex = 0;
        if (!string.IsNullOrEmpty(currentCursor))
        {
            int foundIndex = activeModelIds.IndexOf(currentCursor);
            if (foundIndex >= 0)
            {
                currentIndex = foundIndex;
            }
        }

        var assignedResults = new List<AssignedTaskDto>();
        var assignedPairs = new List<(TrainingTask Task, Trainer Trainer)>();
        int trainerIndex = 0;

        // 5. Fair round-robin assignment loop
        while (trainerIndex < availableTrainers.Count && activeModelIds.Count > 0)
        {
            if (currentIndex >= activeModelIds.Count)
            {
                currentIndex = 0;
            }

            var modelId = activeModelIds[currentIndex];
            var queue = modelQueues[modelId];

            var task = queue.Dequeue();
            var trainer = availableTrainers[trainerIndex];

            // Atomic assignment on entity state
            task.TrainerNodeId = trainer.TrainerNodeId;
            trainer.Status = TrainerStatus.BUSY;
            assignedPairs.Add((task, trainer));

            assignedResults.Add(new AssignedTaskDto
            {
                TrainingTaskId = task.TrainingTaskId,
                ModelId = task.ModelId,
                TrainerNodeId = trainer.TrainerNodeId,
                ShardId = task.ShardId,
                SubmitTime = task.SubmitTime
            });

            trainerIndex++;

            if (queue.Count == 0)
            {
                // Model exhausted pending tasks: prune from active rotation
                activeModelIds.RemoveAt(currentIndex);
                // currentIndex now points to next model or needs wrap
            }
            else
            {
                currentIndex++;
            }
        }

        // 6. Update in-memory cursor state for next invocation
        if (activeModelIds.Count == 0)
        {
            _cursorState.Reset();
        }
        else
        {
            if (currentIndex >= activeModelIds.Count)
            {
                currentIndex = 0;
            }
            _cursorState.SetCurrentCursor(activeModelIds[currentIndex]);
        }

        // 7. Persist atomic assignment within a single database transaction
        if (assignedResults.Count > 0)
        {
            await _dbContext.SaveChangesAsync(ct);
            _logger.LogInformation("Successfully assigned {Count} tasks to idle trainers.", assignedResults.Count);
        }

        // 8. Push StartTrainingCommand to newly assigned busy trainers
        if (assignedPairs.Count > 0)
        {
            _logger.LogInformation("[SchedulerService] Dispatching StartTrainingCommand to {Count} assigned trainer(s)...", assignedPairs.Count);
            foreach (var (assignedTask, assignedTrainer) in assignedPairs)
            {
                var command = new StartTrainingCommand
                {
                    ClientNodeId = assignedTask.ClientNodeId,
                    ModelId = assignedTask.ModelId,
                    ModelVersion = assignedTask.ModelVersion,
                    DataSetId = assignedTask.DataSetId,
                    ShardId = assignedTask.ShardId
                };

                try
                {
                    _logger.LogInformation(
                        "[SchedulerService] Pushing StartTrainingCommand to Trainer '{TrainerId}' [Task='{TaskId}', Model='{ModelId}', Shard='{ShardId}']",
                        assignedTrainer.TrainerNodeId, assignedTask.TrainingTaskId, assignedTask.ModelId, assignedTask.ShardId);

                    var dispatchResult = await _commandCenter.SendAsync(assignedTrainer.TrainerNodeId, command);
                    if (!dispatchResult.IsSuccess)
                    {
                        _logger.LogWarning(
                            "[SchedulerService] Failed to push StartTrainingCommand to Trainer '{TrainerId}': {Error}. Reverting assignment...",
                            assignedTrainer.TrainerNodeId, dispatchResult.FailureReason);

                        assignedTask.TrainerNodeId = string.Empty;
                        assignedTrainer.Status = TrainerStatus.UNCLEAR;
                        await _dbContext.SaveChangesAsync(ct);

                        assignedResults.RemoveAll(r => r.TrainingTaskId == assignedTask.TrainingTaskId);
                    }
                    else
                    {
                        _logger.LogInformation(
                            "[SchedulerService] Successfully dispatched StartTrainingCommand to Trainer '{TrainerId}'.",
                            assignedTrainer.TrainerNodeId);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex,
                        "[SchedulerService] Exception while pushing StartTrainingCommand to Trainer '{TrainerId}'. Reverting assignment...",
                        assignedTrainer.TrainerNodeId);

                    assignedTask.TrainerNodeId = string.Empty;
                    assignedTrainer.Status = TrainerStatus.UNCLEAR;
                    try
                    {
                        await _dbContext.SaveChangesAsync(ct);
                    }
                    catch (Exception dbEx)
                    {
                        _logger.LogError(dbEx, "[SchedulerService] Failed to persist rollback for task '{TaskId}'.", assignedTask.TrainingTaskId);
                    }

                    assignedResults.RemoveAll(r => r.TrainingTaskId == assignedTask.TrainingTaskId);
                }
            }
        }

        return assignedResults;
    }
    catch (DbUpdateConcurrencyException ex)
    {
        _logger.LogError(ex, "Concurrency conflict during task assignment.");
        return Error.Conflict("Scheduler.ConcurrencyConflict", "A concurrency collision occurred during task assignment.");
    }
    catch (OperationCanceledException ex)
    {
        _logger.LogWarning(ex, "Task assignment operation was canceled.");
        return Error.Unexpected("Scheduler.Canceled", "The scheduling operation was canceled.");
    }
    catch (Exception ex)
    {
        _logger.LogError(ex, "Unexpected error occurred during task scheduling.");
        return Error.Failure("Scheduler.AssignmentFailed", $"An error occurred while assigning tasks: {ex.Message}");
    }
}
}
