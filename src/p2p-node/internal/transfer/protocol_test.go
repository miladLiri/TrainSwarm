package transfer

import (
	"os"
	"path/filepath"
	"testing"
)

func TestOpenLocalFile_WindowsPathsInContainer(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "transfer_test")
	if err != nil {
		t.Fatalf("Failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	// Simulate staged model in subfolder: <workingDir>/<model_id>/<model_file>.tar.gz
	modelID := "19014647-d216-4324-9486-eb2fdfd85575"
	modelFileName := "19014647-d216-4324-9486-eb2fdfd85575_0.tar.gz"
	modelSubDir := filepath.Join(tmpDir, modelID)
	if err := os.MkdirAll(modelSubDir, 0755); err != nil {
		t.Fatalf("Failed to create model subdir: %v", err)
	}
	expectedContent := "test-model-checkpoint-data"
	modelPathOnDisk := filepath.Join(modelSubDir, modelFileName)
	if err := os.WriteFile(modelPathOnDisk, []byte(expectedContent), 0644); err != nil {
		t.Fatalf("Failed to write model file: %v", err)
	}

	// Simulate shard in subfolder: <workingDir>/shards/<dataset_id>/<shard_file>.pt
	datasetID := "7f9fba6d-ae02-4bfd-9846-3c55c881a89d"
	shardSubDir := filepath.Join(tmpDir, "shards", datasetID)
	if err := os.MkdirAll(shardSubDir, 0755); err != nil {
		t.Fatalf("Failed to create shard subdir: %v", err)
	}
	shardFileName := "shard_1.pt"
	shardPathOnDisk := filepath.Join(shardSubDir, shardFileName)
	if err := os.WriteFile(shardPathOnDisk, []byte("test-shard-data"), 0644); err != nil {
		t.Fatalf("Failed to write shard file: %v", err)
	}

	mgr := &Manager{workingDir: tmpDir}

	testCases := []struct {
		name        string
		inputPath   string
		expectError bool
	}{
		{
			name:        "Windows host backslash model path on drive E",
			inputPath:   `E:\WorkSpace\TrainSwarm\samples\tiny_stories_training_test\work\client_artifacts\` + modelID + `\` + modelFileName,
			expectError: false,
		},
		{
			name:        "Windows host forward-slash model path on drive E",
			inputPath:   `E:/WorkSpace/TrainSwarm/samples/tiny_stories_training_test/work/client_artifacts/` + modelID + `/` + modelFileName,
			expectError: false,
		},
		{
			name:        "Windows host backslash shard path on drive E",
			inputPath:   `E:\WorkSpace\TrainSwarm\samples\tiny_stories_training_test\work\client_artifacts\shards\` + datasetID + `\` + shardFileName,
			expectError: false,
		},
		{
			name:        "Direct baseName fallback match",
			inputPath:   `C:\some\other\path\` + modelFileName,
			expectError: false,
		},
		{
			name:        "Non-existent file",
			inputPath:   `E:\WorkSpace\TrainSwarm\samples\tiny_stories_training_test\work\client_artifacts\missing\missing.tar.gz`,
			expectError: true,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			f, err := mgr.openLocalFile(tc.inputPath)
			if tc.expectError {
				if err == nil {
					f.Close()
					t.Fatalf("Expected error for %s, but got nil", tc.inputPath)
				}
			} else {
				if err != nil {
					t.Fatalf("Failed to open %s: %v", tc.inputPath, err)
				}
				defer f.Close()
				buf := make([]byte, 64)
				n, _ := f.Read(buf)
				if n == 0 {
					t.Fatalf("Expected non-empty file read for %s", tc.inputPath)
				}
			}
		})
	}
}
