namespace TrainSwarm.Coordinator.Domain.Entities;

public class Trainer
{
    public Guid Id { get; set; }
    
    public DateTime LastContact { get; set; }
    
    public Guid NodeId { get; set; } 
    
    public TrainingSession TrainingSession { get; set; }
}