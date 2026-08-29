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

# 1. Run Owner (Node A)
Write-Host "`n[1/3] Starting Owner (Node A) in background..."
$ownerJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    .\venv\Scripts\Activate.ps1
    python owner.py 50051 "test_file.txt"
} -ArgumentList $ScriptDir

# Give the owner a moment to start
Start-Sleep -Seconds 2

# 2. Run Requester (Node B)
Write-Host "`n[2/3] Starting Requester (Node B)..."
python requester.py 50052 $PeerId "test_file.txt" "localhost"

Write-Host "`n[3/3] Waiting for owner to finish..."
Receive-Job $ownerJob -Wait

Write-Host "`n--- Owner Logs ---"
Receive-Job $ownerJob

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
