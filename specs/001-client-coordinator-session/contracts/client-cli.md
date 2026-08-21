# Client Console Application Contract

**Feature**: `001-client-coordinator-session`
**Date**: 2026-08-21
**Status**: Complete

## 1. Startup & Environment

The Client console application starts by loading `.env` configuration via `config.py`:
- `COORDINATOR_URL`: e.g. `http://localhost:5000`
- `CLIENT_NODE_ID`: e.g. `client-node-01`
- `REQUEST_TIMEOUT_SECONDS`: e.g. `5.0`

On launch, the banner and active configuration are displayed:
```text
========================================
       TrainSwarm Client Console        
========================================
Node ID:         client-node-01
Coordinator URL: http://localhost:5000
Active Session:  None
========================================
```

---

## 2. Interactive Menu Interface

The application runs a continuous REPL loop:

```text
Commands:
  1. Create Training Session
  2. Show Active Session
  3. Exit

Select an option [1-3]: 
```

### 2.1 Command: Create Training Session (Option 1)

1. Prompts for optional session name:
   ```text
   Enter session name (leave blank for auto-generated): 
   ```
2. Sends HTTP POST request to `{COORDINATOR_URL}/api/sessions` with payload:
   ```json
   {
     "clientNodeId": "client-node-01",
     "name": "User-Provided-Name" (or null if blank)
   }
   ```
3. **Success Response Handling**:
   - Updates `ClientNode.active_session` in memory.
   - Outputs:
     ```text
     [SUCCESS] Session created successfully!
     Session ID: 3fa85f64-5717-4562-b3fc-2c963f66afa6
     Name:       User-Provided-Name
     Status:     NONE
     ```
4. **Error Response Handling**:
   - Displays user-friendly failure reason (e.g. connection refused, 400 Bad Request, timeout) without terminating the application:
     ```text
     [ERROR] Failed to create session: Cannot connect to Coordinator at http://localhost:5000 (Connection refused)
     ```

### 2.2 Command: Show Active Session (Option 2)

- If session exists:
  ```text
  Active Session Details:
    Session ID: 3fa85f64-5717-4562-b3fc-2c963f66afa6
    Name:       User-Provided-Name
    Status:     NONE
  ```
- If no session exists:
  ```text
  No active session. Use option 1 to create a session.
  ```

### 2.3 Command: Exit (Option 3)

- Cleanly terminates the console application with return code `0`.