using Microsoft.AspNetCore.Mvc;
using TrainSwarm.Coordinator.Domain.Services;


namespace TrainSwarm.Coordinator.Api.Controllers;


[ApiController]
[Route("api/[controller]")]
public class TrainersController(TrainerService trainerService) : ControllerBase
{
    // GET /api/trainers/instruction?trainerId=...
    [HttpGet("instruction")]
    public async Task<ActionResult<TrainerInstructionResponse>> GetInstruction([FromQuery] Guid? trainerId)
    {
        var result = await trainerService.GetInstructionAsync(trainerId);
        return Ok(result);
    }
}
