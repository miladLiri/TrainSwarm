using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace TrainSwarm.Coordinator.Infrastructure.Persistence.Migrations
{
    /// <inheritdoc />
    public partial class InitialTrainingTask : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "TrainingTasks",
                columns: table => new
                {
                    TrainingTaskId = table.Column<Guid>(type: "TEXT", nullable: false),
                    ClientNodeId = table.Column<string>(type: "TEXT", nullable: false),
                    ModelId = table.Column<string>(type: "TEXT", nullable: false),
                    ModelVersion = table.Column<string>(type: "TEXT", nullable: false),
                    DataSetId = table.Column<string>(type: "TEXT", nullable: false),
                    ShardId = table.Column<string>(type: "TEXT", nullable: false),
                    TrainerNodeId = table.Column<string>(type: "TEXT", nullable: false, defaultValue: "")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_TrainingTasks", x => x.TrainingTaskId);
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "TrainingTasks");
        }
    }
}
