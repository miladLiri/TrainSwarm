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
}
