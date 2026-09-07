using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using ErrorOr;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using TrainSwarm.Coordinator.Application.Contracts;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Application.Services;

public class SchedulerService
{
    private readonly ICoordinatorDbContext _dbContext;
    private readonly ISchedulerCursorState _cursorState;
    private readonly ILogger<SchedulerService> _logger;

    public SchedulerService(
        ICoordinatorDbContext dbContext,
        ISchedulerCursorState cursorState,
        ILogger<SchedulerService> logger)
    {
        _dbContext = dbContext;
        _cursorState = cursorState;
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
