using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Application.Contracts;

public interface ICoordinatorDbContext
{
    DbSet<TrainingTask> TrainingTasks { get; }
    Task<int> SaveChangesAsync(CancellationToken ct = default);
}
