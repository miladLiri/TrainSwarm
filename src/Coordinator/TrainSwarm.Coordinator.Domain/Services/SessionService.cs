using Microsoft.EntityFrameworkCore;
using TrainSwarm.Coordinator.Domain.Context;
using TrainSwarm.Coordinator.Domain.Entities;


namespace TrainSwarm.Coordinator.Domain.Services;


public class SessionService(CoordinatorDbContext dbContext)
{
    public async Task<TrainingSession> CreateSessionAsync(TrainingSession session)
    {
        if (string.IsNullOrWhiteSpace(session.ClientNodeId))
        {
            throw new ArgumentException("ClientNodeId cannot be null or empty.", nameof(session.ClientNodeId));
        }

        if (string.IsNullOrWhiteSpace(session.Name))
        {
            session.Name = $"Session-{DateTime.UtcNow:yyyyMMddHHmmss}";
        }

        if (session.Id == Guid.Empty)
            session.Id = Guid.NewGuid();

        session.Status = SessionStatus.WAITING;

        dbContext.TrainingSessions.Add(session);
        await dbContext.SaveChangesAsync();

        return session;
    }
    
    public async Task<IEnumerable<TrainingSession>> GetAllSessionsAsync()
    {
        return await dbContext.TrainingSessions.ToListAsync();
    }

    public async Task<TrainingSession> GetSessionByIdAsync(Guid id)
    {
        return await dbContext.TrainingSessions.FindAsync(id);
    }
    

    public async Task<bool> CancelSessionAsync(Guid id)
    {
        var session = await dbContext.TrainingSessions.FindAsync(id);
        if (session == null) return false;

        session.Status = SessionStatus.CANCELLED;
        
        await dbContext.SaveChangesAsync();
        return true;
    }

    public async Task<SessionStatus> GetSessionStatusAsync(Guid id)
    {
        var session = await dbContext.TrainingSessions
            .Select(s => new { s.Id, s.Status })
            .FirstOrDefaultAsync(s => s.Id == id);

        return session?.Status ??  SessionStatus.NONE;
    }
}
