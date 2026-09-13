namespace TrainSwarm.Coordinator.Application.Services;

public class DetachTrainerRequest
{
    public string TrainerNodeId { get; set; } = string.Empty;
    public bool IsTrainingComplete { get; set; }
}

public class DetachTrainerResult
{
    public string TrainerNodeId { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;

    public DetachTrainerResult() { }

    public DetachTrainerResult(string trainerNodeId, string status, string message)
    {
        TrainerNodeId = trainerNodeId;
        Status = status;
        Message = message;
    }
}
