"""Presentation layer for the Trainer console application."""

import sys
from application.trainer_service import TrainerService
from infrastructure.bootstrap_client import BootstrapError


class ConsoleUI:
    """Provides the interactive console interface and REPL menu loop for Trainer."""

    def __init__(self, trainer_service: TrainerService):
        self.trainer_service = trainer_service

    def print_banner(self) -> None:
        state = self.trainer_service.trainer_state
        peer_id_str = state.peer_id if state.peer_id else "None (Unregistered)"
        status_str = state.status.value

        print("========================================")
        print("       TrainSwarm Trainer Console       ")
        print("========================================")
        print(f"Node ID:         {state.node_id}")
        print(f"Peer ID:         {peer_id_str}")
        print(f"Bootstrap URL:   {state.bootstrap_url}")
        print(f"Coordinator URL: {state.coordinator_url}")
        print(f"Relay Status:    {status_str}")
        print("========================================")

    def print_menu(self) -> None:
        print("\nCommands:")
        print("  1. View Node & Network Status")
        print("  2. Reconnect to Bootstrap Relay")
        print("  3. List Discovered Peers")
        print("  4. Check Coordinator Status")
        print("  5. Exit")

    def run(self) -> None:
        """Runs the interactive command loop."""
        self.print_banner()

        while True:
            self.print_menu()
            try:
                choice = input("\nSelect an option [1-5]: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting TrainSwarm Trainer...")
                break

            if choice == "1":
                self._handle_view_status()
            elif choice == "2":
                self._handle_reconnect_bootstrap()
            elif choice == "3":
                self._handle_list_peers()
            elif choice == "4":
                self._handle_check_coordinator()
            elif choice == "5":
                print("Exiting TrainSwarm Trainer...")
                break
            else:
                print("[WARN] Invalid option. Please enter a number between 1 and 5.")

    def _handle_view_status(self) -> None:
        state = self.trainer_service.trainer_state
        peer_id_str = state.peer_id if state.peer_id else "None"
        print("\n----------------------------------------")
        print("Trainer Node Status:")
        print(f"  Node ID:         {state.node_id}")
        print(f"  Peer ID:         {peer_id_str}")
        print(f"  Bootstrap URL:   {state.bootstrap_url}")
        print(f"  Coordinator URL: {state.coordinator_url}")
        print(f"  Relay Status:    {state.status.value}")
        print("----------------------------------------")

    def _handle_reconnect_bootstrap(self) -> None:
        print(f"\n[INFO] Connecting to Bootstrap Relay at {self.trainer_service.trainer_state.bootstrap_url}...")
        try:
            peer_session = self.trainer_service.register_with_bootstrap()
            print("\n----------------------------------------")
            print("[SUCCESS] Registered with Bootstrap Relay!")
            print(f"  Assigned Peer ID: {peer_session.peer_id}")
            print(f"  Relay Address:    {peer_session.relay_address}")
            print("----------------------------------------")
        except BootstrapError as e:
            print(f"\n[ERROR] {str(e)}")
        except Exception as e:
            print(f"\n[ERROR] Unexpected error connecting to Bootstrap: {str(e)}")

    def _handle_list_peers(self) -> None:
        print("\n[INFO] Querying active swarm peers from Bootstrap...")
        try:
            peers = self.trainer_service.list_peers()
            my_peer_id = self.trainer_service.trainer_state.peer_id
            print("\n----------------------------------------")
            print(f"Discovered Peers in Swarm ({len(peers)}):")
            if not peers:
                print("  (No peers currently registered)")
            else:
                for p in peers:
                    p_id = p.get("peerId", "unknown")
                    n_id = p.get("nodeId", "unknown")
                    role = p.get("role", "unknown")
                    self_marker = " [Self]" if p_id == my_peer_id else ""
                    print(f"  - [{role}] {n_id} (Peer ID: {p_id}){self_marker}")
            print("----------------------------------------")
        except BootstrapError as e:
            print(f"\n[ERROR] Failed to query peers: {str(e)}")
        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {str(e)}")

    def _handle_check_coordinator(self) -> None:
        print(f"\n[INFO] Checking Coordinator at {self.trainer_service.trainer_state.coordinator_url}...")
        res = self.trainer_service.check_coordinator_health()
        if res.get("reachable"):
            print(f"[SUCCESS] Coordinator is reachable (Status: {res.get('status_code')}).")
        else:
            print(f"[WARN] Coordinator is unreachable: {res.get('error')}")

