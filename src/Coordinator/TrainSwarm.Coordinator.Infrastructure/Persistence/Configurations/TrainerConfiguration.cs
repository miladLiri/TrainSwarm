using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using TrainSwarm.Coordinator.Domain.Entities;

namespace TrainSwarm.Coordinator.Infrastructure.Persistence.Configurations;

public class TrainerConfiguration : IEntityTypeConfiguration<Trainer>
{
    public void Configure(EntityTypeBuilder<Trainer> builder)
    {
        builder.ToTable("Trainers");

        builder.HasKey(t => t.Id);

        builder.Property(t => t.TrainerNodeId)
            .IsRequired()
            .HasMaxLength(128);

        builder.Property(t => t.Status)
            .IsRequired()
            .HasConversion<int>();
    }
}
