package relay

import (
	"crypto/rand"
	"fmt"
	"os"

	"github.com/libp2p/go-libp2p/core/crypto"
)

func LoadOrGenerateIdentity(path string) (crypto.PrivKey, error) {
	if _, err := os.Stat(path); os.IsNotExist(err) {
		// Generate new key
		priv, _, err := crypto.GenerateEd25519Key(rand.Reader)
		if err != nil {
			return nil, fmt.Errorf("failed to generate identity key: %w", err)
		}

		keyBytes, err := crypto.MarshalPrivateKey(priv)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal identity key: %w", err)
		}

		if err := os.WriteFile(path, keyBytes, 0600); err != nil {
			return nil, fmt.Errorf("failed to save identity key: %w", err)
		}

		return priv, nil
	}

	// Load existing key
	keyBytes, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read identity key: %w", err)
	}

	priv, err := crypto.UnmarshalPrivateKey(keyBytes)
	if err != nil {
		return nil, fmt.Errorf("failed to unmarshal identity key: %w", err)
	}

	return priv, nil
}
