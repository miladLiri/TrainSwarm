"""Presentation layer for the Client console application."""

import sys
from application.session_service import SessionService
from infrastructure.coordinator_client import CoordinatorError
from infrastructure.bootstrap_client import BootstrapError


class ConsoleUI:
    """Provides the interactive console interface and REPL menu loop for Client."""

    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    def print_banner(self) -> None:
        state = self.session_service.client_state
        active = state.active_session
        session_str = f"{active.name} ({active.session_id})" if active else "None"
        peer_id_str = state.peer_id if state.peer_id else "None (Unregistered)"

        print("========================================")
        print("       TrainSwarm Client Console        ")
        print("========================================")
        print(f"Node ID:         {state.node_id}")
        print(f"Peer ID:         {peer_id_str}")
        print(f"Bootstrap URL:   {state.bootstrap_url}")
        print(f"Coordinator URL: {state.coordinator_url}")
        print(f"Active Session:  {session_str}")
        print("========================================")

    def print_menu(self) -> None:
        print("\nCommands:")
        print("  1. Create Training Session")
        print("  2. Show Active Session & Node Status")
        print("  3. Reconnect to Bootstrap Relay")
        print("  4. List Discovered Peers")
        print("  5. Exit")

    def run(self) -> None:
        """Runs the interactive command loop."""
        self.print_banner()

        while True:
            self.print_menu()
            try:
                choice = input("\nSelect an option [1-5]: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting TrainSwarm Client...")
                break

            if choice == "1":
                self._handle_create_session()
            elif choice == "2":
                self._handle_show_active_session()
            elif choice == "3":
                self._handle_reconnect_bootstrap()
            elif choice == "4":
                self._handle_list_peers()
            elif choice == "5":
                print("Exiting TrainSwarm Client...")
                break
            else:
                print("[WARN] Invalid option. Please enter a number between 1 and 5.")

    def _handle_create_session(self) -> None:
        try:
            name_input = input("Enter session name (leave blank for auto-generated): ").strip()
            name = name_input if name_input else None

            print("\n[INFO] Contacting Coordinator to create session...")
            session = self.session_service.create_session(name=name)

            print("\n----------------------------------------")
            print("[SUCCESS] Session created successfully!")
            print(f"  Session ID: {session.session_id}")
            print(f"  Name:       {session.name}")
            print(f"  Status:     {session.status}")
            print("----------------------------------------")
        except CoordinatorError as e:
            print(f"\n[ERROR] {str(e)}")
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred: {str(e)}")

    def _handle_show_active_session(self) -> None:
        state = self.session_service.client_state
        active = self.session_service.get_active_session()
        peer_id_str = state.peer_id if state.peer_id else "None (Unregistered)"

        print("\n----------------------------------------")
        print("Client Node & Session Status:")
        print(f"  Node ID:         {state.node_id}")
        print(f"  Peer ID:         {peer_id_str}")
        print(f"  Bootstrap URL:   {state.bootstrap_url}")
        print(f"  Coordinator URL: {state.coordinator_url}")
        if active:
            print(f"  Active Session ID:     {active.session_id}")
            print(f"  Active Session Name:   {active.name}")
            print(f"  Active Session Status: {active.status}")
        else:
            print("  Active Session:  None (Use option 1 to create a session)")
        print("----------------------------------------")

    def _handle_reconnect_bootstrap(self) -> None:
        print(f"\n[INFO] Connecting to Bootstrap Relay at {self.session_service.client_state.bootstrap_url}...")
        try:
            data = self.session_service.register_with_bootstrap()
            print("\n----------------------------------------")
            print("[SUCCESS] Registered with Bootstrap Relay!")
            print(f"  Assigned Peer ID: {data.get('peerId')}")
            print(f"  Relay Address:    {data.get('relayAddress')}")
            print("----------------------------------------")
        except BootstrapError as e:
            print(f"\n[ERROR] {str(e)}")
        except Exception as e:
            print(f"\n[ERROR] Unexpected error connecting to Bootstrap: {str(e)}")

    def _handle_list_peers(self) -> None:
        print("\n[INFO] Querying active swarm peers from Bootstrap...")
        try:
            peers = self.session_service.list_peers()
            my_peer_id = self.session_service.client_state.peer_id
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