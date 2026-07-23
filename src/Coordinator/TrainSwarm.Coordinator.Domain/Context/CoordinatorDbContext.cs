using Microsoft.EntityFrameworkCore;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Domain.Context;

public class CoordinatorDbContext(DbContextOptions<CoordinatorDbContext> options) : DbContext(options)
{
    public DbSet<TrainingSession> TrainingSessions { get; set; }
    public DbSet<Trainer> Trainers { get; set; }
    
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<TrainingSession>(entity =>
        {
            entity.HasKey(x => x.Id);
            
            entity.Property(x => x.Name)
                .IsRequired()
                .HasMaxLength(200);
            
            entity.Property(x => x.Status)
                .HasConversion<string>() 
                .IsRequired();
            
            entity.Property(x => x.ClientNodeId)
                .IsRequired();

            entity.HasMany(x => x.Trainers)
                .WithOne(x => x.TrainingSession)
                .OnDelete(DeleteBehavior.SetNull);
        });

        modelBuilder.Entity<Trainer>(entity =>
        {
            
            entity.HasKey(x => x.Id);

            entity.Property(x => x.LastContact)
                .IsRequired();

            entity.Property(x => x.NodeId)
                .IsRequired();
        });
        
        base.OnModelCreating(modelBuilder);
    }
}