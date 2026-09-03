using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.ModelBinding;
using TrainSwarm.Coordinator.Application.Services;

namespace TrainSwarm.Coordinator.Api.Controllers;

[ApiController]
[Route("api/training-tasks")]
public class TrainingTaskController : ControllerBase
{
    private readonly TrainingTaskService _trainingTaskService;

    public TrainingTaskController(TrainingTaskService trainingTaskService)
    {
        _trainingTaskService = trainingTaskService;
    }

    [HttpPost]
    [ProducesResponseType(typeof(CreateTrainingTaskResponseDto), StatusCodes.Status201Created)]
    [ProducesResponseType(typeof(ValidationProblemDetails), StatusCodes.Status400BadRequest)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> CreateTrainingTasks([FromBody] CreateTrainingTaskDto request, CancellationToken ct = default)
    {
        var result = await _trainingTaskService.CreateTrainingTaskAsync(request, ct);

        if (result.IsError)
        {
            var modelState = new ModelStateDictionary();
            foreach (var error in result.Errors)
            {
                modelState.AddModelError(error.Code, error.Description);
            }
            return ValidationProblem(modelState);
        }

        var response = new CreateTrainingTaskResponseDto
        {
            TrainingTaskIds = result.Value.TrainingTaskIds.Select(id => id.ToString()).ToList()
        };

        return StatusCode(StatusCodes.Status201Created, response);
    }
}
