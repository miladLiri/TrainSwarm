using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using TrainSwarm.Coordinator.Application.Services;

namespace TrainSwarm.Coordinator.Api.Controllers;

[ApiController]
[Route("api/trainers")]
public class TrainerController : ControllerBase
{
    private readonly TrainerService _trainerService;

    public TrainerController(TrainerService trainerService)
    {
        _trainerService = trainerService;
    }

    [HttpPost("connect")]
    [ProducesResponseType(typeof(ConnectTrainerResponseDto), StatusCodes.Status200OK)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> ConnectTrainer([FromBody] ConnectTrainerDto request, CancellationToken ct = default)
    {
        var result = await _trainerService.ConnectTrainerAsync(request, ct);

        if (result.IsError)
        {
            var modelState = new ModelStateDictionary();
            foreach (var error in result.Errors)
            {
                modelState.AddModelError(error.Code, error.Description);
            }
            return ValidationProblem(modelState);
        }

        var response = new ConnectTrainerResponseDto
        {
            Id = result.Value.Id.ToString(),
            TrainerNodeId = result.Value.TrainerNodeId,
            Status = result.Value.Status.ToString()
        };

        return Ok(response);
    }

    [HttpPost("clear")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> ClearTrainers(CancellationToken ct = default)
    {
        var result = await _trainerService.ClearTrainersAsync(ct);
        if (result.IsError)
        {
            return StatusCode(StatusCodes.Status500InternalServerError, new { error = result.FirstError.Description });
        }
        return Ok(new { message = "All trainers cleared." });
    }
}
