using System.Collections.Generic;

namespace TrainSwarm.Coordinator.Api.Controllers;

public class CreateTrainingTaskResponseDto
{
    public List<string> TrainingTaskIds { get; set; } = new();
}
