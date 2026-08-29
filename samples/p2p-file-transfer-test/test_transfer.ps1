param (
    [Parameter(Mandatory=$true)]
    [string]$PeerId,
    [switch]$KeepEnv = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

.\venv\Scripts\Activate.ps1

# Create a sample file
$sampleContent = "Hello from Node A! This is a P2P file transfer test across simulated NATs."
Set-Content -Path "test_file.txt" -Value $sampleContent
if (Test-Path "received_test_file.txt") { Remove-Item "received_test_file.txt" }

# 1. Run Sender (Node A)
Write-Host "`n[1/3] Starting Sender (Node A) in background..."
$senderJob = Start-Job -ScriptBlock {
    param($dir, $peerId)
    Set-Location $dir
    .\venv\Scripts\Activate.ps1
    python sender.py 50051 $peerId "test_file.txt" "localhost"
} -ArgumentList $ScriptDir, $PeerId

# Give the sender a moment to initiate the connection
Start-Sleep -Seconds 2

# 2. Run Receiver (Node B)
Write-Host "`n[2/3] Starting Receiver (Node B)..."
python receiver.py 50052

Write-Host "`n[3/3] Waiting for sender to finish..."
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
