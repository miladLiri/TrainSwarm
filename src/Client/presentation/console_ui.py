"""Presentation layer for the Client console application."""

import sys
from application.session_service import SessionService
from infrastructure.coordinator_client import CoordinatorError


class ConsoleUI:
    """Provides the interactive console interface and REPL menu loop."""

    def __init__(self, session_service: SessionService):
        self.session_service = session_service

    def print_banner(self) -> None:
        state = self.session_service.client_state
        active = state.active_session
        session_str = f"{active.name} ({active.session_id})" if active else "None"

        print("========================================")
        print("       TrainSwarm Client Console        ")
        print("========================================")
        print(f"Node ID:         {state.node_id}")
        print(f"Coordinator URL: {state.coordinator_url}")
        print(f"Active Session:  {session_str}")
        print("========================================")

    def print_menu(self) -> None:
        print("\nCommands:")
        print("  1. Create Training Session")
        print("  2. Show Active Session")
        print("  3. Exit")

    def run(self) -> None:
        """Runs the interactive command loop."""
        self.print_banner()

        while True:
            self.print_menu()
            try:
                choice = input("\nSelect an option [1-3]: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nExiting TrainSwarm Client...")
                break

            if choice == "1":
                self._handle_create_session()
            elif choice == "2":
                self._handle_show_active_session()
            elif choice == "3":
                print("Exiting TrainSwarm Client...")
                break
            else:
                print("[WARN] Invalid option. Please enter 1, 2, or 3.")

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
        active = self.session_service.get_active_session()
        if active:
            print("\n----------------------------------------")
            print("Active Session Details:")
            print(f"  Session ID:      {active.session_id}")
            print(f"  Name:            {active.name}")
            print(f"  Client Node ID:  {active.client_node_id}")
            print(f"  Status:          {active.status}")
            print("----------------------------------------")
        else:
            print("\n[INFO] No active session. Use option 1 to create a session.")