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
docker-compose down -v 2>$null

# 1. Start Relay
Write-Host "`n[1/5] Starting Relay node..."
docker-compose up -d --build relay

# 2. Wait for Relay Peer ID
$peerId = $null
Write-Host "Waiting for relay to generate Peer ID..."
while ($null -eq $peerId) {
    Start-Sleep -Seconds 2
    $logs = docker-compose logs relay
    if ($logs -match 'peer_id="([^"]+)"') {
        $peerId = $Matches[1]
    }
}
Write-Host "Relay Peer ID: $peerId"

# 3. Start Nodes
$env:RELAY_MULTIADDR = "/dns4/host.docker.internal/tcp/4001/p2p/$peerId"
Write-Host "`n[2/5] Starting Node A and Node B..."
Write-Host "Using Relay Addr: $env:RELAY_MULTIADDR"
docker-compose up -d --build node-a node-b

Start-Sleep -Seconds 5

# 5. Get Node B's Peer ID
$nodeBPeerId = $null
Write-Host "Fetching Node B Peer ID..."
while ($null -eq $nodeBPeerId) {
    Start-Sleep -Seconds 1
    $logs = docker-compose logs node-b
    if ($logs -match 'P2P Node ID: ([a-zA-Z0-9]+)') {
        $nodeBPeerId = $Matches[1]
    }
}
Write-Host "Node B Peer ID: $nodeBPeerId"

# Create a sample file
$sampleContent = "Hello from Node A! This is a P2P file transfer test across simulated NATs."
Set-Content -Path "test_file.txt" -Value $sampleContent
if (Test-Path "received_test_file.txt") { Remove-Item "received_test_file.txt" }

# 6. Run Receiver (Node B)
Write-Host "`n[3/5] Starting Receiver (Node B) in background..."
$receiverJob = Start-Job -ScriptBlock {
    param($nodeBId, $dir)
    Set-Location $dir
    .\venv\Scripts\Activate.ps1
    python receiver.py 50052 $nodeBId
} -ArgumentList $nodeBPeerId, $ScriptDir

Start-Sleep -Seconds 3

# 7. Run Sender (Node A)
Write-Host "`n[4/5] Starting Sender (Node A)..."
python sender.py 50051 $nodeBPeerId "test_file.txt" $peerId

Write-Host "`n[5/5] Waiting for receiver to finish..."
Start-Sleep -Seconds 5

Write-Host "`n--- Receiver Logs ---"
Receive-Job $receiverJob

# Verify
if (Test-Path "received_test_file.txt") {
    $received = Get-Content "received_test_file.txt"
    Write-Host "`n✅ SUCCESS! File transferred correctly. Content: '$received'" -ForegroundColor Green
} else {
    Write-Host "`n❌ FAILED! File was not received." -ForegroundColor Red
}

if (-not $KeepEnv) {
    Write-Host "`nCleaning up docker environment..."
    docker-compose down -v
} else {
    Write-Host "`nEnvironment kept running. Use 'docker-compose down' to clean up later."
}
