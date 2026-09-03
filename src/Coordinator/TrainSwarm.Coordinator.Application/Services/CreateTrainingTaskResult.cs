using System;
using System.Collections.Generic;
using System.Linq;

namespace TrainSwarm.Coordinator.Application.Services;

public class CreateTrainingTaskResult
{
    public IReadOnlyList<Guid> TrainingTaskIds { get; }

    public CreateTrainingTaskResult(IEnumerable<Guid> trainingTaskIds)
    {
        TrainingTaskIds = trainingTaskIds != null ? trainingTaskIds.ToList().AsReadOnly() : new List<Guid>().AsReadOnly();
    }
}
