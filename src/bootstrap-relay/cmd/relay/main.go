package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"bootstrap-relay/internal/config"
	"bootstrap-relay/internal/relay"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("level=error msg=\"failed to load config\" err=\"%v\"", err)
	}

	// Logging based on level
	if cfg.LogLevel == "debug" {
		log.SetFlags(log.LstdFlags | log.Lshortfile)
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Load or Generate Identity
	priv, err := relay.LoadOrGenerateIdentity(cfg.IdentityPath)
	if err != nil {
		log.Fatalf("level=error msg=\"failed to setup identity\" err=\"%v\"", err)
	}
	log.Printf("level=info msg=\"Identity loaded\" path=\"%s\"", cfg.IdentityPath)

	// Create LibP2P Host
	h, err := relay.NewHost(ctx, priv, cfg)
	if err != nil {
		log.Fatalf("level=error msg=\"failed to create host\" err=\"%v\"", err)
	}
	defer h.Close()

	// Initialize Circuit Relay v2 Service
	relayService, err := relay.NewRelayService(h, cfg)
	if err != nil {
		log.Fatalf("level=error msg=\"failed to start relay service\" err=\"%v\"", err)
	}
	defer relayService.Close()

	log.Printf("level=info msg=\"Relay started\" peer_id=\"%s\"", h.ID().String())
	for _, addr := range h.Addrs() {
		log.Printf("level=info msg=\"Listening on\" addr=\"%s/p2p/%s\"", addr.String(), h.ID().String())
	}

	go func() {
		http.HandleFunc("/peerid", func(w http.ResponseWriter, r *http.Request) {
			w.Write([]byte(h.ID().String()))
		})
		log.Println("level=info msg=\"Starting HTTP server for PeerID\"")
		if err := http.ListenAndServe(fmt.Sprintf(":%s", cfg.ListenHTTP), nil); err != nil {
			log.Fatalf("level=error msg=\"HTTP server failed\" err=\"%v\"", err)
		}
	}()

	// Wait for interrupt signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	<-sigCh
	log.Println("level=info msg=\"Shutting down relay...\"")

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer shutdownCancel()

	if err := relayService.Close(); err != nil {
		log.Printf("level=error msg=\"error closing relay service\" err=\"%v\"", err)
	}
	if err := h.Close(); err != nil {
		log.Printf("level=error msg=\"error closing host\" err=\"%v\"", err)
	} else {
		log.Println("level=info msg=\"Shutdown complete\"")
	}

	<-shutdownCtx.Done()
}
