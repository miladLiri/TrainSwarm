using Microsoft.AspNetCore.Mvc;
using TrainSwarm.Coordinator.Application.Commands;

namespace TrainSwarm.Coordinator.Api.Controllers;

public record DispatchStartTrainingDto(
    string TrainerId,
    string ClientNodeId,
    string ModelId,
    string ModelVersion,
    string DataSetId,
    string ShardId
);

[ApiController]
[Route("api/[controller]")]
public class CommandDispatchController(ICommandCenter commandCenter) : ControllerBase
{
    [HttpPost("start-training")]
    public async Task<ActionResult<CommandDispatchResult>> DispatchStartTraining([FromBody] DispatchStartTrainingDto dto)
    {
        if (string.IsNullOrWhiteSpace(dto.TrainerId))
        {
            return BadRequest("TrainerId is required.");
        }

        var command = new StartTrainingCommand
        {
            ClientNodeId = dto.ClientNodeId,
            ModelId = dto.ModelId,
            ModelVersion = dto.ModelVersion,
            DataSetId = dto.DataSetId,
            ShardId = dto.ShardId
        };

        var result = await commandCenter.SendAsync(dto.TrainerId, command);
        if (!result.IsSuccess)
        {
            return StatusCode(503, result);
        }

        return Ok(result);
    }
}
