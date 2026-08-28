param (
    [switch]$KeepEnv = $false
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

# Clean up any old runs
docker compose down -v 2>$null

# 1. Start Relay
Write-Host "`n[1/5] Starting Relay node..."
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
Write-Host "`n[2/5] Starting Node A and Node B..."
docker compose up -d --build node-a node-b

Start-Sleep -Seconds 5

# 5. Get Node B's Peer ID
$nodeBPeerId = $null
Write-Host "Fetching Node B Peer ID via gRPC..."
while ([string]::IsNullOrEmpty($nodeBPeerId)) {
    Start-Sleep -Seconds 1
    try {
        $nodeBPeerId = python receiver.py 50052 --get-peer-id 2>$null
    } catch {
        # ignore errors until gRPC is up
    }
}
Write-Host "Node B Peer ID: $nodeBPeerId"

# Create a sample file
$sampleContent = "Hello from Node A! This is a P2P file transfer test across simulated NATs."
Set-Content -Path "test_file.txt" -Value $sampleContent
if (Test-Path "received_test_file.txt") { Remove-Item "received_test_file.txt" }

# 6. Run Sender (Node A)
Write-Host "`n[3/5] Starting Sender (Node A) in background..."
$senderJob = Start-Job -ScriptBlock {
    param($dir, $peerId)
    Set-Location $dir
    .\venv\Scripts\Activate.ps1
    python sender.py 50051 $peerId "test_file.txt" "localhost"
} -ArgumentList $ScriptDir, $nodeBPeerId

# Give the sender a moment to initiate the connection
Start-Sleep -Seconds 2

# 7. Run Receiver (Node B)
Write-Host "`n[4/5] Starting Receiver (Node B)..."
python receiver.py 50052

Write-Host "`n[5/5] Waiting for sender to finish..."
Receive-Job $senderJob -Wait

Write-Host "`n--- Sender Logs ---"
Receive-Job $senderJob

# Verify
if (Test-Path "received_test_file.txt") {
    $received = Get-Content "received_test_file.txt"
    Write-Host "`n✅ SUCCESS! File transferred correctly. Content: '$received'" -ForegroundColor Green
} else {
    Write-Host "`n❌ FAILED! File was not received." -ForegroundColor Red
}

if (-not $KeepEnv) {
    Write-Host "`nCleaning up docker environment..."
    docker compose down -v
} else {
    Write-Host "`nEnvironment kept running. Use '.\stop.ps1' or 'docker compose down' to clean up later."
}
