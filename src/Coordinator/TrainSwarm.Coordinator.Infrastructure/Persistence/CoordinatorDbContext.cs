using Microsoft.EntityFrameworkCore;
using TrainSwarm.Coordinator.Application.Contracts;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Infrastructure.Persistence;

public class CoordinatorDbContext : DbContext, ICoordinatorDbContext
{
    public CoordinatorDbContext(DbContextOptions<CoordinatorDbContext> options)
        : base(options)
    {
    }

    public DbSet<TrainingTask> TrainingTasks { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(CoordinatorDbContext).Assembly);
    }
}
