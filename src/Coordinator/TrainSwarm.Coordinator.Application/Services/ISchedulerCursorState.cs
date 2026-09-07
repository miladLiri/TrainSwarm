namespace TrainSwarm.Coordinator.Application.Services;

public interface ISchedulerCursorState
{
    string GetCurrentCursor();
    void SetCurrentCursor(string modelId);
    void Reset();
}
