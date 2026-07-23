# run-dev.ps1
$Host.UI.RawUI.WindowTitle = "Development Runner - SQL Server & Coordinator API"
Clear-Host

# Config database variables
$DbServer = "localhost,1433"
$DbName = "TrainSwarmCoordinator"
$DbUser = "sa"
$DbPassword = "YourStrong@Pass123"
$ContainerName = "trainswarm-coordinator-sql"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "[1/3] Checking Docker SQL Server Container..." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# Check if container exists (running or stopped)
$containerExists = docker ps -a --filter "name=^/${ContainerName}$" --format "{{.Names}}"

if ([string]::IsNullOrEmpty($containerExists)) {
    Write-Host "Container '$ContainerName' does not exist. Creating a new one..." -ForegroundColor Yellow
    docker run -d `
      --name $ContainerName `
      -e "ACCEPT_EULA=Y" `
      -e "MSSQL_SA_PASSWORD=$DbPassword" `
      -p 1433:1433 `
      -v sql_data:/var/opt/mssql `
      mcr.microsoft.com/mssql/server
} else {
    # Check if container is already running
    $containerRunning = docker ps --filter "name=^/${ContainerName}$" --format "{{.Names}}"
    if ([string]::IsNullOrEmpty($containerRunning)) {
        Write-Host "Container '$ContainerName' is stopped. Starting it..." -ForegroundColor Yellow
        docker start $ContainerName
    } else {
        Write-Host "Container '$ContainerName' is already running." -ForegroundColor Green
    }
}

Write-Host "`n===================================================" -ForegroundColor Cyan
Write-Host "[2/3] Setting up Environment Variables..." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# Set environment variables for the current PowerShell process
$env:DB_SERVER = $DbServer
$env:DB_NAME = $DbName
$env:DB_USER = $DbUser
$env:DB_PASSWORD = $DbPassword

Write-Host "Environment variables set in process scope." -ForegroundColor Green

Write-Host "`n===================================================" -ForegroundColor Cyan
Write-Host "[3/3] Launching Coordinator Api..." -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# Wait 3 seconds to ensure SQL Server is ready to accept local connections
Start-Sleep -Seconds 3

dotnet run --project .\TrainSwarm.Coordinator.Api

Write-Host "`nPress any key to exit..."
[void]$Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
