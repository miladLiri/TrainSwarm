using Microsoft.AspNetCore.Mvc;
using TrainSwarm.Coordinator.Domain.Entities;
using TrainSwarm.Coordinator.Domain.Services;

namespace TrainSwarm.Coordinator.Api.Controllers;



[ApiController]
[Route("api/[controller]")]
public class SessionsController(SessionService sessionService) : ControllerBase
{
    // GET /api/sessions
    [HttpGet]
    public async Task<ActionResult<IEnumerable<TrainingSession>>> GetSessions()
    {
        var sessions = await sessionService.GetAllSessionsAsync();
        return Ok(sessions);
    }

    // GET /api/sessions/{sessionId}
    [HttpGet("{sessionId:guid}")]
    public async Task<ActionResult<TrainingSession>> GetSession(Guid sessionId)
    {
        var session = await sessionService.GetSessionByIdAsync(sessionId);
        if (session == null)
        {
            return NotFound($"Session with ID {sessionId} not found.");
        }
        return Ok(session);
    }
    

    // POST /api/sessions/{sessionId}/cancel
    [HttpPost("{sessionId:guid}/cancel")]
    public async Task<IActionResult> CancelSession(Guid sessionId)
    {
        var success = await sessionService.CancelSessionAsync(sessionId);
        if (!success)
        {
            return NotFound($"Session with ID {sessionId} not found.");
        }
        return NoContent();
    }

    // GET /api/sessions/{sessionId}/status
    [HttpGet("{sessionId:guid}/status")]
    public async Task<ActionResult<object>> GetSessionStatus(Guid sessionId)
    {
        var status = await sessionService.GetSessionStatusAsync(sessionId);
        if (status == SessionStatus.NONE)
        {
            return NotFound($"Session with ID {sessionId} not found.");
        }
        
        return Ok(new { SessionId = sessionId, Status = status.ToString() });
    }
    
    // POST /api/sessions
    [HttpPost]
    public async Task<ActionResult<TrainingSession>> AddSession([FromBody] CreateSessionDto request)
    {
        if (request == null || string.IsNullOrWhiteSpace(request.ClientNodeId))
        {
            return BadRequest(new { error = "ClientNodeId is required and cannot be empty." });
        }

        var session = new TrainingSession
        {
            Name = request.Name?.Trim() ?? string.Empty,
            ClientNodeId = request.ClientNodeId.Trim()
        };

        var createdSession = await sessionService.CreateSessionAsync(session);

        return CreatedAtAction(
            nameof(GetSession),
            new { sessionId = createdSession.Id },
            createdSession);
    }
}
