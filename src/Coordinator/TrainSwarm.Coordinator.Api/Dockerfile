FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS base
WORKDIR /app
EXPOSE 8080
EXPOSE 8081
RUN mkdir -p /data && chown -R $APP_UID /data
VOLUME ["/data"]
ENV COORDINATOR_DB_CONNECTION_STRING="Data Source=/data/coordinator.db"
USER $APP_UID

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src
COPY ["TrainSwarm.Coordinator.Domain/TrainSwarm.Coordinator.Domain.csproj", "TrainSwarm.Coordinator.Domain/"]
COPY ["TrainSwarm.Coordinator.Application/TrainSwarm.Coordinator.Application.csproj", "TrainSwarm.Coordinator.Application/"]
COPY ["TrainSwarm.Coordinator.Infrastructure/TrainSwarm.Coordinator.Infrastructure.csproj", "TrainSwarm.Coordinator.Infrastructure/"]
COPY ["TrainSwarm.Coordinator.Api/TrainSwarm.Coordinator.Api.csproj", "TrainSwarm.Coordinator.Api/"]
RUN dotnet restore "TrainSwarm.Coordinator.Api/TrainSwarm.Coordinator.Api.csproj"
COPY . .
WORKDIR "/src/TrainSwarm.Coordinator.Api"
RUN dotnet build "./TrainSwarm.Coordinator.Api.csproj" -c $BUILD_CONFIGURATION -o /app/build

FROM build AS publish
ARG BUILD_CONFIGURATION=Release
RUN dotnet publish "./TrainSwarm.Coordinator.Api.csproj" -c $BUILD_CONFIGURATION -o /app/publish /p:UseAppHost=false

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "TrainSwarm.Coordinator.Api.dll"]
