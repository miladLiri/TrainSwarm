$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "Stopping and removing test containers..."
docker compose down -v

# Clean up jobs if any
Get-Job | Where-Object { $_.State -ne 'Running' } | Remove-Job

Write-Host "Cleanup complete." -ForegroundColor Green
