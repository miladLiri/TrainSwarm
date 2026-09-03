using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Infrastructure.Persistence.Configurations;

public class TrainingTaskConfiguration : IEntityTypeConfiguration<TrainingTask>
{
    public void Configure(EntityTypeBuilder<TrainingTask> builder)
    {
        builder.ToTable("TrainingTasks");

        builder.HasKey(t => t.TrainingTaskId);

        builder.Property(t => t.ClientNodeId)
            .IsRequired();

        builder.Property(t => t.ModelId)
            .IsRequired();

        builder.Property(t => t.ModelVersion)
            .IsRequired();

        builder.Property(t => t.DataSetId)
            .IsRequired();

        builder.Property(t => t.ShardId)
            .IsRequired();

        builder.Property(t => t.TrainerNodeId)
            .IsRequired()
            .HasDefaultValue(string.Empty);
    }
}
