using System.Collections.Generic;

namespace TrainSwarm.Coordinator.Application.Services;

public class CreateTrainingTaskDto
{
    public string ClientNodeId { get; set; }
    public string ModelId { get; set; }
    public string ModelVersion { get; set; }
    public string DataSetId { get; set; }
    public List<string> ShardIdList { get; set; }
}
