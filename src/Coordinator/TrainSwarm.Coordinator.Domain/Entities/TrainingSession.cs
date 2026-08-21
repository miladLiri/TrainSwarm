namespace TrainSwarm.Coordinator.Domain.Entities;

public class TrainingSession
{
    public Guid Id { get; set; }    
    
    public string Name { get; set; } = string.Empty; 

    public SessionStatus Status { get; set; } = SessionStatus.NONE;
    
    public string ClientNodeId { get; set; } = string.Empty;
     
    public ICollection<Trainer> Trainers { get; set; } = new List<Trainer>();
}