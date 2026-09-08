using System;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using TrainSwarm.Coordinator.Api.Grpc;
using TrainSwarm.Coordinator.Application.Commands;
using TrainSwarm.Coordinator.Application.Services;
using TrainSwarm.Coordinator.Infrastructure;
using Microsoft.AspNetCore.Server.Kestrel.Core;
using TrainSwarm.Coordinator.Infrastructure.Persistence;

var builder = WebApplication.CreateBuilder(args);

var httpPortStr = Environment.GetEnvironmentVariable("COORDINATOR_HTTP_PORT");
var grpcPortStr = Environment.GetEnvironmentVariable("COORDINATOR_GRPC_PORT");
var aspnetUrls = Environment.GetEnvironmentVariable("ASPNETCORE_URLS");

int httpPort = 5050;
if (int.TryParse(httpPortStr, out var hp))
{
    httpPort = hp;
}
else if (!string.IsNullOrWhiteSpace(aspnetUrls))
{
    foreach (var url in aspnetUrls.Split(';', StringSplitOptions.RemoveEmptyEntries))
    {
        if (Uri.TryCreate(url, UriKind.Absolute, out var uri) && uri.Port > 0)
        {
            httpPort = uri.Port;
            break;
        }
    }
}

int grpcPort = int.TryParse(grpcPortStr, out var gp) ? gp : (httpPort + 1);

builder.WebHost.ConfigureKestrel(options =>
{
    options.ListenAnyIP(httpPort, listenOptions =>
    {
        listenOptions.Protocols = HttpProtocols.Http1;
    });
    options.ListenAnyIP(grpcPort, listenOptions =>
    {
        listenOptions.Protocols = HttpProtocols.Http2;
    });
});

builder.Services.AddOpenApi();

var connectionString = Environment.GetEnvironmentVariable("COORDINATOR_DB_CONNECTION_STRING");
if (string.IsNullOrWhiteSpace(connectionString))
{
    throw new InvalidOperationException("COORDINATOR_DB_CONNECTION_STRING environment variable is missing or empty.");
}

builder.Services.AddCoordinatorPersistenceServices(connectionString);

builder.Services.AddSingleton<ISchedulerCursorState, SchedulerCursorState>();
builder.Services.AddScoped<TrainingTaskService>();
builder.Services.AddScoped<TrainerService>();
builder.Services.AddScoped<SchedulerService>();

builder.Services.AddGrpc();
builder.Services.AddSingleton<ITrainerConnectionManager, TrainerConnectionManager>();
builder.Services.AddSingleton<ICommandCenter, CommandCenter>();

builder.Services.AddControllers();

var app = builder.Build();

app.MapGrpcService<CoordinatorCommandServiceImpl>();
app.MapControllers();
app.MapOpenApi();
app.MapGet("/health", () => Results.Ok(new { status = "Healthy" }));

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<CoordinatorDbContext>();
    db.Database.Migrate();
}

app.Run();
