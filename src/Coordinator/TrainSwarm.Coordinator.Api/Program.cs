using Microsoft.EntityFrameworkCore;
using TrainSwarm.Coordinator.Domain.Context;
using TrainSwarm.Coordinator.Domain.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenApi();

var dbServer = Environment.GetEnvironmentVariable("DB_SERVER");
var dbName = Environment.GetEnvironmentVariable("DB_NAME");
var dbUser = Environment.GetEnvironmentVariable("DB_USER");
var dbPassword = Environment.GetEnvironmentVariable("DB_PASSWORD");

if (string.IsNullOrWhiteSpace(dbServer) ||
    string.IsNullOrWhiteSpace(dbName) ||
    string.IsNullOrWhiteSpace(dbUser) ||
    string.IsNullOrWhiteSpace(dbPassword))
{
    throw new Exception("Database environment variables are not fully configured.");
}

string connectionString =
    $"Server={dbServer};Database={dbName};User Id={dbUser};Password={dbPassword};TrustServerCertificate=True;Encrypt=False;";


builder.Services.AddDbContext<CoordinatorDbContext>(options => options.UseSqlServer(connectionString));

builder.Services.AddScoped<SessionService>();
builder.Services.AddScoped<TrainerService>();

builder.Services.AddEndpointsApiExplorer();

builder.Services.AddControllers();

var app = builder.Build();


app.MapControllers();   
app.MapOpenApi();
 

app.UseHttpsRedirection();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<CoordinatorDbContext>();
    db.Database.Migrate();
}

app.Run();

