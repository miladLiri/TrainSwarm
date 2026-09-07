namespace TrainSwarm.Coordinator.Application.Services;

public class SchedulerCursorState : ISchedulerCursorState
{
    private readonly object _lock = new object();
    private string _currentModelId;

    public string GetCurrentCursor()
    {
        lock (_lock)
        {
            return _currentModelId;
        }
    }

    public void SetCurrentCursor(string modelId)
    {
        lock (_lock)
        {
            _currentModelId = modelId;
        }
    }

    public void Reset()
    {
        lock (_lock)
        {
            _currentModelId = null;
        }
    }
}
