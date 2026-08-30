using Microsoft.AspNetCore.Mvc;
using TrainSwarm.Coordinator.Domain.Commands;

namespace TrainSwarm.Coordinator.Api.Controllers;

public record DispatchStartTrainingDto(
    string TrainerId,
    string TrainingClientNodeId,
    string SessionId
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
            TrainingClientNodeId = dto.TrainingClientNodeId,
            SessionId = dto.SessionId
        };

        var result = await commandCenter.SendAsync(dto.TrainerId, command);
        if (!result.IsSuccess)
        {
            return StatusCode(503, result);
        }

        return Ok(result);
    }
}
