using System;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using TrainSwarm.Coordinator.Application.Contracts;
using TrainSwarm.Coordinator.Infrastructure.Persistence;

namespace TrainSwarm.Coordinator.Infrastructure;

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddCoordinatorPersistenceServices(this IServiceCollection services, string connectionString)
    {
        if (string.IsNullOrWhiteSpace(connectionString))
        {
            throw new InvalidOperationException("COORDINATOR_DB_CONNECTION_STRING is missing or empty.");
        }

        services.AddDbContext<CoordinatorDbContext>(options =>
            options.UseSqlite(connectionString));

        services.AddScoped<ICoordinatorDbContext>(sp =>
            sp.GetRequiredService<CoordinatorDbContext>());

        return services;
    }
}
