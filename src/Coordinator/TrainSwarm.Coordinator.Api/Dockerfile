FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS base
USER $APP_UID
WORKDIR /app
EXPOSE 8080
EXPOSE 8081

FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src
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
