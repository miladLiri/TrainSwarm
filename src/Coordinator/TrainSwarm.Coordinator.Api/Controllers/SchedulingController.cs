using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using ErrorOr;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;
using TrainSwarm.Coordinator.Application.Services;

namespace TrainSwarm.Coordinator.Api.Controllers;

[ApiController]
[Route("api/scheduler")]
public class SchedulingController : ControllerBase
{
    private readonly SchedulerService _schedulerService;
    private readonly ILogger<SchedulingController> _logger;

    public SchedulingController(SchedulerService schedulerService, ILogger<SchedulingController> logger)
    {
        _schedulerService = schedulerService;
        _logger = logger;
    }

    [HttpPost("assign")]
    [ProducesResponseType(typeof(List<AssignedTaskDto>), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status409Conflict)]
    [ProducesResponseType(StatusCodes.Status500InternalServerError)]
    public async Task<IActionResult> AssignTasks(CancellationToken ct = default)
    {
        try
        {
            var result = await _schedulerService.AssignTasksAsync(ct);

            if (result.IsError)
            {
                var firstError = result.FirstError;
                _logger.LogWarning("Task assignment failed with error code: {Code}, description: {Description}",
                    firstError.Code, firstError.Description);

                if (firstError.Type == ErrorType.Conflict)
                {
                    return StatusCode(StatusCodes.Status409Conflict, new { error = firstError.Description, code = firstError.Code });
                }

                if (firstError.Type == ErrorType.Validation)
                {
                    return StatusCode(StatusCodes.Status400BadRequest, new { error = firstError.Description, code = firstError.Code });
                }

                return StatusCode(StatusCodes.Status500InternalServerError, new { error = firstError.Description, code = firstError.Code });
            }

            return Ok(result.Value);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unhandled exception occurred while processing task assignment.");
            return StatusCode(StatusCodes.Status500InternalServerError, new
            {
                error = "An unexpected error occurred while assigning tasks.",
                detail = ex.Message
            });
        }
    }
}
