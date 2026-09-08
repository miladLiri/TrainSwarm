using System.Text.Json.Serialization;

namespace TrainSwarm.Coordinator.Application.Commands;

public class StartTrainingCommand
{
    [JsonPropertyName("clientNodeId")]
    public string ClientNodeId { get; set; } = string.Empty;

    [JsonPropertyName("modelId")]
    public string ModelId { get; set; } = string.Empty;

    [JsonPropertyName("modelVersion")]
    public string ModelVersion { get; set; } = string.Empty;

    [JsonPropertyName("dataSetId")]
    public string DataSetId { get; set; } = string.Empty;

    [JsonPropertyName("shardId")]
    public string ShardId { get; set; } = string.Empty;
}
