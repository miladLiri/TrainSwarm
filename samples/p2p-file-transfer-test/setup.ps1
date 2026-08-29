param (
    [switch]$ForceClean = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# Create python venv if not exists
if (-not (Test-Path venv)) {
    Write-Host "Creating Python virtual environment..."
    python -m venv venv
}
.\venv\Scripts\Activate.ps1
pip install -q grpcio grpcio-tools

# Generate stubs
Write-Host "Generating gRPC Python stubs from protobuf..."
python -m grpc_tools.protoc -I ../../specs/004-go-p2p-sidecar/contracts --python_out=. --grpc_python_out=. ../../specs/004-go-p2p-sidecar/contracts/p2p.proto

if ($ForceClean) {
    # Clean up any old runs
    docker compose down -v 2>$null
}

# 1. Start Relay
Write-Host "`n[1/3] Starting Relay node..."
docker compose up -d --build relay

# 2. Wait for Relay HTTP API
Write-Host "Waiting for relay HTTP API on port 8090..."
while ($true) {
    try {
        $relayPeerId = Invoke-RestMethod -Uri "http://localhost:8090/peerid" -ErrorAction Stop
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
Write-Host "Relay Peer ID from HTTP API: $relayPeerId"

# 3. Start Nodes
Write-Host "`n[2/3] Starting Node A and Node B..."
docker compose up -d --build node-a node-b

Start-Sleep -Seconds 5

Write-Host "`n[3/3] Setup complete! Services are running."
