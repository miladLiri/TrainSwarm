package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	ListenTCP        string
	ListenQUIC       string
	IdentityPath     string
	MaxReservations  int
	MaxCircuits      int
	MaxRelayedBytes  int64
	MaxRelayDuration time.Duration
	LogLevel         string
}

func Load() (*Config, error) {
	cfg := &Config{
		ListenTCP:        getEnv("P2P_RELAY_LISTEN_TCP", ""),
		ListenQUIC:       getEnv("P2P_RELAY_LISTEN_QUIC", ""),
		IdentityPath:     getEnv("P2P_RELAY_IDENTITY_PATH", ""),
		MaxReservations:  getEnvInt("P2P_RELAY_MAX_RESERVATIONS", 128),
		MaxCircuits:      getEnvInt("P2P_RELAY_MAX_CIRCUITS", 16),
		MaxRelayedBytes:  int64(getEnvInt("P2P_RELAY_MAX_RELAYED_BYTES", 10485760)), // 10MB
		MaxRelayDuration: getEnvDuration("P2P_RELAY_MAX_RELAY_DURATION", 2*time.Minute),
		LogLevel:         getEnv("P2P_RELAY_LOG_LEVEL", "info"),
	}

	if cfg.ListenTCP == "" {
		return nil, fmt.Errorf("P2P_RELAY_LISTEN_TCP is required")
	}
	if cfg.IdentityPath == "" {
		return nil, fmt.Errorf("P2P_RELAY_IDENTITY_PATH is required")
	}

	return cfg, nil
}

func getEnv(key, defaultVal string) string {
	if val, ok := os.LookupEnv(key); ok {
		return val
	}
	return defaultVal
}

func getEnvInt(key string, defaultVal int) int {
	if val, ok := os.LookupEnv(key); ok {
		if intVal, err := strconv.Atoi(val); err == nil {
			return intVal
		}
	}
	return defaultVal
}

func getEnvDuration(key string, defaultVal time.Duration) time.Duration {
	if val, ok := os.LookupEnv(key); ok {
		if durVal, err := time.ParseDuration(val); err == nil {
			return durVal
		}
	}
	return defaultVal
}
