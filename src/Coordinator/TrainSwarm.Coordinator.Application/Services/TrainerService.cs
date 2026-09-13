using System;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using ErrorOr;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using TrainSwarm.Coordinator.Application.Contracts;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Application.Services;

public class TrainerService
{
    private readonly ICoordinatorDbContext _dbContext;
    private readonly ILogger<TrainerService> _logger;

    public TrainerService(ICoordinatorDbContext dbContext, ILogger<TrainerService> logger)
    {
        _dbContext = dbContext;
        _logger = logger;
    }

    public async Task<ErrorOr<Success>> ClearTrainersAsync(CancellationToken ct = default)
    {
        try
        {
            var trainers = await _dbContext.Trainers.ToListAsync(ct);
            if (trainers.Count > 0)
            {
                _dbContext.Trainers.RemoveRange(trainers);
                await _dbContext.SaveChangesAsync(ct);
            }

            _logger.LogInformation("Successfully cleared {Count} trainer(s).", trainers.Count);
            return Result.Success;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to clear trainers.");
            return Error.Failure("Trainers.ClearFailed", "Failed to clear trainers.");
        }
    }

    public async Task<ErrorOr<ConnectTrainerResult>> ConnectTrainerAsync(
        ConnectTrainerDto request,
        CancellationToken ct = default)
    {
        if (request == null)
        {
            return Error.Validation("Invalid.Request", "Request body cannot be null.");
        }

        var trainerNodeId = request.TrainerNodeId?.Trim();
        if (string.IsNullOrWhiteSpace(trainerNodeId))
        {
            _logger.LogWarning("Trainer connection rejected: TrainerNodeId is required.");
            return Error.Validation("Invalid.TrainerNodeId", "TrainerNodeId cannot be null, empty, or whitespace.");
        }

        try
        {
            // Remove any existing records matching the TrainerNodeId
            var existingTrainers = await _dbContext.Trainers
                .Where(t => t.TrainerNodeId == trainerNodeId)
                .ToListAsync(ct);

            if (existingTrainers.Count > 0)
            {
                _logger.LogInformation("Removing {Count} existing record(s) for TrainerNodeId={TrainerNodeId}",
                    existingTrainers.Count, trainerNodeId);
                _dbContext.Trainers.RemoveRange(existingTrainers);
            }

            // Insert new trainer record with IDLE status
            var newTrainer = new Trainer
            {
                Id = Guid.NewGuid(),
                TrainerNodeId = trainerNodeId,
                Status = request.Status ?? TrainerStatus.IDLE
            };

            await _dbContext.Trainers.AddAsync(newTrainer, ct);
            await _dbContext.SaveChangesAsync(ct);

            _logger.LogInformation("Trainer connected successfully with Id={TrainerId}, TrainerNodeId={TrainerNodeId}, Status={Status}",
                newTrainer.Id, newTrainer.TrainerNodeId, newTrainer.Status);

            return new ConnectTrainerResult(newTrainer.Id, newTrainer.TrainerNodeId, newTrainer.Status);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to connect trainer for TrainerNodeId={TrainerNodeId}", trainerNodeId);
            return Error.Failure("Trainer.ConnectionFailed", "An error occurred while saving trainer connection.");
        }
    }

    public async Task<ErrorOr<DetachTrainerResult>> DetachTrainerAsync(
        DetachTrainerRequest request,
        CancellationToken ct = default)
    {
        if (request == null)
        {
            return Error.Validation("Invalid.Request", "Request body cannot be null.");
        }

        var trainerNodeId = request.TrainerNodeId?.Trim();
        if (string.IsNullOrWhiteSpace(trainerNodeId))
        {
            _logger.LogWarning("DetachTrainer rejected: TrainerNodeId is required.");
            return Error.Validation("Invalid.TrainerNodeId", "TrainerNodeId cannot be null, empty, or whitespace.");
        }

        try
        {
            var trainer = await _dbContext.Trainers
                .FirstOrDefaultAsync(t => t.TrainerNodeId == trainerNodeId, ct);

            if (trainer == null)
            {
                _logger.LogInformation("DetachTrainer: TrainerNodeId={TrainerNodeId} not found; returning success no-op.", trainerNodeId);
                return new DetachTrainerResult(trainerNodeId, TrainerStatus.IDLE.ToString(), "Trainer not found; no-op success.");
            }

            if (trainer.Status != TrainerStatus.BUSY)
            {
                _logger.LogInformation("DetachTrainer: TrainerNodeId={TrainerNodeId} status is {Status} (not BUSY); returning success no-op.",
                    trainerNodeId, trainer.Status);
                return new DetachTrainerResult(trainerNodeId, trainer.Status.ToString(), "Trainer is not busy; no state change needed.");
            }

            // Status is BUSY
            if (request.IsTrainingComplete)
            {
                trainer.Status = TrainerStatus.IDLE;
            }
            else
            {
                trainer.Status = TrainerStatus.UNCLEAR;
            }

            await _dbContext.SaveChangesAsync(ct);
            _logger.LogInformation("DetachTrainer: TrainerNodeId={TrainerNodeId} transitioned to {Status} (IsTrainingComplete={IsComplete})",
                trainerNodeId, trainer.Status, request.IsTrainingComplete);

            return new DetachTrainerResult(trainerNodeId, trainer.Status.ToString(), $"Trainer status transitioned to {trainer.Status}.");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to detach trainer for TrainerNodeId={TrainerNodeId}", trainerNodeId);
            return Error.Failure("Trainer.DetachFailed", "An error occurred while detaching trainer.");
        }
    }

    public async Task<ErrorOr<System.Collections.Generic.List<TrainerDto>>> GetTrainersAsync(CancellationToken ct = default)
    {
        try
        {
            var trainers = await _dbContext.Trainers
                .AsNoTracking()
                .Select(t => new TrainerDto
                {
                    Id = t.Id,
                    TrainerNodeId = t.TrainerNodeId,
                    Status = t.Status.ToString()
                })
                .ToListAsync(ct);

            return trainers;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to retrieve trainers.");
            return Error.Failure("Trainers.QueryFailed", "Failed to retrieve trainers.");
        }
    }
}
