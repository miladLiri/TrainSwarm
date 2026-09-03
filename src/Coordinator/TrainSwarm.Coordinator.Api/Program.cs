using System;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using TrainSwarm.Coordinator.Api.Grpc;
using TrainSwarm.Coordinator.Application.Commands;
using TrainSwarm.Coordinator.Application.Services;
using TrainSwarm.Coordinator.Infrastructure;
using TrainSwarm.Coordinator.Infrastructure.Persistence;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenApi();

var connectionString = Environment.GetEnvironmentVariable("COORDINATOR_DB_CONNECTION_STRING");
if (string.IsNullOrWhiteSpace(connectionString))
{
    throw new InvalidOperationException("COORDINATOR_DB_CONNECTION_STRING environment variable is missing or empty.");
}

builder.Services.AddCoordinatorPersistenceServices(connectionString);

builder.Services.AddScoped<TrainingTaskService>();

builder.Services.AddGrpc();
builder.Services.AddSingleton<ITrainerConnectionManager, TrainerConnectionManager>();
builder.Services.AddSingleton<ICommandCenter, CommandCenter>();

builder.Services.AddControllers();

var app = builder.Build();

app.MapGrpcService<CoordinatorCommandServiceImpl>();
app.MapControllers();
app.MapOpenApi();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<CoordinatorDbContext>();
    db.Database.Migrate();
}

app.Run();
