using Microsoft.EntityFrameworkCore;
using TrainSwarm.Coordinator.Domain.Context;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Domain.Services;



public class TrainerService(CoordinatorDbContext dbContext)
{
    public async Task<TrainerInstructionResponse> GetInstructionAsync(Guid? trainerId)
    {
        var now = DateTime.UtcNow;

        Trainer trainer;

        if (trainerId == null)
        {
            trainer = new Trainer
            {
                Id = Guid.NewGuid(),
                LastContact = now,
                NodeId = Guid.Empty
            };

            dbContext.Trainers.Add(trainer);
            await dbContext.SaveChangesAsync();
        }
        else
        {
            trainer = await dbContext.Trainers
                .Include(x => x.TrainingSession)
                .FirstOrDefaultAsync(x => x.Id == trainerId.Value);

            if (trainer == null)
            {
                trainer = new Trainer
                {
                    Id = trainerId.Value,
                    LastContact = now,
                    NodeId = Guid.Empty
                };

                dbContext.Trainers.Add(trainer);
                await dbContext.SaveChangesAsync();
            }
            else
            {
                trainer.LastContact = now;
            }
        }

        var response = new TrainerInstructionResponse
        {
            TrainerId = trainer.Id,
            IsCanceled = false,
            ClientNodeId = null
        };
        
            if (trainer.TrainingSession != null)
            {
                if (trainer.TrainingSession.Status == SessionStatus.CANCELLED)
                {
                    response.IsCanceled = true;
                    trainer.TrainingSession = null;
                }
                else
                {
                    response.ClientNodeId = trainer.TrainingSession.ClientNodeId;
                }
            }

      

        if (trainer.TrainingSession == null)
        {
            var waitingSession = await dbContext.TrainingSessions
                .Where(x => x.Status == SessionStatus.WAITING)
                .OrderBy(x => x.Id)
                .FirstOrDefaultAsync();

            if (waitingSession != null)
            {
                trainer.TrainingSession = waitingSession;
                waitingSession.Status = SessionStatus.ACTIVE;
                response.ClientNodeId = waitingSession.ClientNodeId;
            }
        }

        await dbContext.SaveChangesAsync();

        return response;
    }
}
