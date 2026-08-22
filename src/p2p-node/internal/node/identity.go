package node

import (
	"crypto/rand"
	"fmt"
	"io"
	"os"

	"github.com/libp2p/go-libp2p/core/crypto"
)

// LoadOrGenerateIdentity loads a libp2p ed25519 identity from the given path,
// or generates a new one and saves it if the file does not exist.
func LoadOrGenerateIdentity(keyPath string) (crypto.PrivKey, error) {
	_, err := os.Stat(keyPath)
	if err == nil {
		// File exists, read it
		keyBytes, err := os.ReadFile(keyPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read identity file: %w", err)
		}
		
		priv, err := crypto.UnmarshalPrivateKey(keyBytes)
		if err != nil {
			return nil, fmt.Errorf("failed to unmarshal private key: %w", err)
		}
		return priv, nil
	}
	
	if !os.IsNotExist(err) {
		return nil, fmt.Errorf("failed to stat identity file: %w", err)
	}
	
	// Generate new key
	priv, _, err := crypto.GenerateEd25519Key(rand.Reader)
	if err != nil {
		return nil, fmt.Errorf("failed to generate ed25519 key: %w", err)
	}
	
	// Marshal and save
	keyBytes, err := crypto.MarshalPrivateKey(priv)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal private key: %w", err)
	}
	
	if err := os.WriteFile(keyPath, keyBytes, 0600); err != nil {
		return nil, fmt.Errorf("failed to write identity file: %w", err)
	}
	
	return priv, nil
}
