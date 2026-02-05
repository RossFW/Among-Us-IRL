#!/usr/bin/env python3
"""
Automated game flow testing script.
Tests the refactored Among Us IRL app by simulating multiple players via API calls.
"""

import requests
import json
import time
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass

# Change this to your Cloudflare URL or localhost
BASE_URL = "https://creatures-wholesale-tells-analyzed.trycloudflare.com"
# BASE_URL = "http://localhost:8000"

@dataclass
class Player:
    """Represents a test player"""
    name: str
    session_token: str
    player_id: Optional[str] = None
    role: Optional[str] = None

class GameTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.game_code: Optional[str] = None
        self.players: List[Player] = []
        self.tests_passed = 0
        self.tests_failed = 0

    def log(self, emoji: str, message: str):
        """Pretty print test results"""
        print(f"{emoji} {message}")

    def assert_test(self, condition: bool, test_name: str):
        """Track test results"""
        if condition:
            self.tests_passed += 1
            self.log("✅", test_name)
        else:
            self.tests_failed += 1
            self.log("❌", test_name)

    def create_player(self, name: str) -> Player:
        """Create a player with session token"""
        return Player(name=name, session_token=str(uuid.uuid4()))

    def create_game(self, player: Player) -> bool:
        """Test: Create a new game"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games",
                json={
                    "player_name": player.name,
                    "session_token": player.session_token
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.game_code = data.get("code")
                player.player_id = data.get("player_id")
                # API returns new session token - use that instead
                player.session_token = data.get("session_token")
                self.assert_test(
                    self.game_code and len(self.game_code) == 4,
                    f"Create game (code: {self.game_code})"
                )
                return True
            else:
                self.assert_test(False, f"Create game (status: {response.status_code})")
                return False
        except Exception as e:
            self.assert_test(False, f"Create game (error: {e})")
            return False

    def join_game(self, player: Player) -> bool:
        """Test: Join existing game"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/join",
                json={
                    "player_name": player.name,
                    "session_token": player.session_token
                }
            )

            if response.status_code == 200:
                data = response.json()
                player.player_id = data.get("player_id")
                # API returns new session token - use that instead
                player.session_token = data.get("session_token")
                self.assert_test(
                    player.player_id is not None,
                    f"Player '{player.name}' joined game"
                )
                return True
            else:
                self.assert_test(False, f"Join game as '{player.name}' (status: {response.status_code})")
                return False
        except Exception as e:
            self.assert_test(False, f"Join game as '{player.name}' (error: {e})")
            return False

    def get_game_state(self, player: Player) -> Optional[Dict]:
        """Get current game state"""
        try:
            response = requests.get(
                f"{self.base_url}/api/games/{self.game_code}",
                params={
                    "session_token": player.session_token
                }
            )
            return response.json() if response.status_code == 200 else None
        except:
            return None

    def update_settings(self, host: Player, settings: Dict) -> bool:
        """Test: Update game settings"""
        try:
            response = requests.patch(
                f"{self.base_url}/api/games/{self.game_code}/settings",
                params={"session_token": host.session_token},
                json=settings
            )
            self.assert_test(
                response.status_code == 200,
                f"Update settings: {list(settings.keys())}"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Update settings (error: {e})")
            return False

    def start_game(self, host: Player) -> bool:
        """Test: Start the game"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/start",
                params={"session_token": host.session_token}
            )

            if response.status_code == 200:
                # Get roles for all players
                time.sleep(0.5)  # Let role assignment settle
                for player in self.players:
                    state = self.get_game_state(player)
                    if state and 'players' in state:
                        for p in state['players']:
                            if p['id'] == player.player_id:
                                player.role = p.get('role')
                                break

                self.assert_test(True, f"Start game (roles assigned)")
                return True
            else:
                self.assert_test(False, f"Start game (status: {response.status_code})")
                return False
        except Exception as e:
            self.assert_test(False, f"Start game (error: {e})")
            return False

    def get_player_info(self, player: Player) -> Optional[Dict]:
        """Test: Get player's own info (role, tasks)"""
        try:
            response = requests.get(
                f"{self.base_url}/api/players/me",
                params={"session_token": player.session_token}
            )

            if response.status_code == 200:
                data = response.json()
                self.assert_test(
                    'role' in data,
                    f"Get player info for '{player.name}' (role: {data.get('role')})"
                )
                return data
            else:
                self.assert_test(False, f"Get player info (status: {response.status_code})")
                return None
        except Exception as e:
            self.assert_test(False, f"Get player info (error: {e})")
            return None

    def complete_task(self, player: Player, task_id: str) -> bool:
        """Test: Complete a task"""
        try:
            response = requests.post(
                f"{self.base_url}/api/tasks/{task_id}/complete",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"Complete task '{task_id}' for '{player.name}'"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Complete task (error: {e})")
            return False

    def start_meeting(self, player: Player, is_body_report: bool = False) -> bool:
        """Test: Start a meeting"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/meeting/start",
                params={"session_token": player.session_token},
                json={"is_body_report": is_body_report}
            )
            meeting_type = "body report" if is_body_report else "meeting"
            self.assert_test(
                response.status_code == 200,
                f"Start {meeting_type} by '{player.name}'"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Start meeting (error: {e})")
            return False

    def start_voting(self, player: Player) -> bool:
        """Test: Start voting phase"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/meeting/start_voting",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"Start voting phase"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Start voting (error: {e})")
            return False

    def cast_vote(self, player: Player, target_id: Optional[str] = None) -> bool:
        """Test: Cast a vote (None = skip)"""
        try:
            params = {"session_token": player.session_token}
            if target_id:
                params["target_id"] = target_id

            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/vote",
                params=params
            )
            vote_type = f"for player {target_id[:4]}..." if target_id else "skip"
            self.assert_test(
                response.status_code == 200,
                f"'{player.name}' voted {vote_type}"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Cast vote (error: {e})")
            return False

    def end_meeting(self, player: Player) -> bool:
        """Test: End meeting"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/meeting/end",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"End meeting"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"End meeting (error: {e})")
            return False

    def mark_dead(self, player: Player, target_id: str) -> bool:
        """Test: Mark a player as dead"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/players/{target_id}/die",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"Mark player dead"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Mark dead (error: {e})")
            return False

    def captain_meeting(self, player: Player) -> bool:
        """Test: Captain ability - remote meeting"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/ability/captain-meeting",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"Captain '{player.name}' called remote meeting"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Captain meeting (error: {e})")
            return False

    def engineer_fix(self, player: Player) -> bool:
        """Test: Engineer ability - remote fix"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/ability/engineer-fix",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"Engineer '{player.name}' fixed remotely"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Engineer fix (error: {e})")
            return False

    def start_sabotage(self, player: Player, sabotage_index: int) -> bool:
        """Test: Start a sabotage (1=Lights, 2=Reactor, 3=O2, 4=Comms)"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/sabotage/start",
                params={
                    "session_token": player.session_token,
                    "sabotage_index": sabotage_index
                }
            )
            sabotage_names = {1: "Lights", 2: "Reactor", 3: "O2", 4: "Comms"}
            sabotage_name = sabotage_names.get(sabotage_index, f"sabotage #{sabotage_index}")
            self.assert_test(
                response.status_code == 200,
                f"Start '{sabotage_name}' sabotage"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Start sabotage (error: {e})")
            return False

    def fix_sabotage(self, player: Player) -> bool:
        """Test: Fix active sabotage"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/sabotage/fix",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"Fix sabotage"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Fix sabotage (error: {e})")
            return False

    def print_summary(self):
        """Print test summary"""
        total = self.tests_passed + self.tests_failed
        print("\n" + "="*60)
        print(f"TEST SUMMARY")
        print("="*60)
        print(f"✅ Passed: {self.tests_passed}/{total}")
        print(f"❌ Failed: {self.tests_failed}/{total}")

        if self.tests_failed == 0:
            print("\n🎉 All tests passed!")
        else:
            print(f"\n⚠️  {self.tests_failed} test(s) failed - check output above")

        print("\n📋 Next: Update TESTING.md with results")
        print("="*60)


def test_voting_scenarios():
    """Test various voting outcomes"""
    print("\n" + "="*60)
    print("🗳️  VOTING SCENARIOS TEST SUITE")
    print("="*60)

    tester = GameTester(BASE_URL)

    # Test 1: Everyone skips
    print("\n📍 TEST: Everyone skips vote")
    print("-" * 60)
    host = tester.create_player("Host")
    p2 = tester.create_player("Player2")
    p3 = tester.create_player("Player3")
    p4 = tester.create_player("Player4")

    if tester.create_game(host):
        for p in [p2, p3, p4]:
            tester.join_game(p)
        tester.players = [host, p2, p3, p4]

        if tester.start_game(host):
            # Start meeting
            if tester.start_meeting(host):
                time.sleep(0.5)
                if tester.start_voting(host):
                    time.sleep(6)  # Wait for discussion

                    # Everyone skips
                    for player in tester.players:
                        tester.cast_vote(player, target_id=None)

                    time.sleep(1)

                    # Check result - no one should be eliminated
                    state = tester.get_game_state(host)
                    alive_count = sum(1 for p in state['players'] if p['status'] == 'alive')
                    tester.assert_test(
                        alive_count == 4,
                        "Everyone skips → no elimination (4 players still alive)"
                    )

                    tester.end_meeting(host)

    # Test 2: Majority votes for one player
    print("\n📍 TEST: Majority votes for one player")
    print("-" * 60)
    tester2 = GameTester(BASE_URL)
    host2 = tester2.create_player("Host2")
    p2_2 = tester2.create_player("Player2")
    p3_2 = tester2.create_player("Player3")
    p4_2 = tester2.create_player("Player4")

    if tester2.create_game(host2):
        for p in [p2_2, p3_2, p4_2]:
            tester2.join_game(p)
        tester2.players = [host2, p2_2, p3_2, p4_2]

        if tester2.start_game(host2):
            # Get player IDs
            for player in tester2.players:
                info = tester2.get_player_info(player)
                player.player_id = info['id'] if info else player.player_id

            # Start meeting
            if tester2.start_meeting(host2):
                time.sleep(0.5)
                if tester2.start_voting(host2):
                    time.sleep(6)  # Wait for discussion

                    # 3 vote for p2_2, 1 skips
                    target_id = p2_2.player_id
                    tester2.cast_vote(host2, target_id=target_id)
                    tester2.cast_vote(p3_2, target_id=target_id)
                    tester2.cast_vote(p4_2, target_id=target_id)
                    tester2.cast_vote(p2_2, target_id=None)  # Target votes skip

                    time.sleep(1)

                    # Check result - p2_2 should be eliminated
                    state = tester2.get_game_state(host2)
                    eliminated_player = next((p for p in state['players'] if p['id'] == target_id), None)
                    tester2.assert_test(
                        eliminated_player and eliminated_player['status'] == 'dead',
                        "Majority votes → player eliminated (target is dead)"
                    )

                    tester2.end_meeting(host2)

    # Test 3: Tie vote
    print("\n📍 TEST: Tie vote (2v2)")
    print("-" * 60)
    tester3 = GameTester(BASE_URL)
    host3 = tester3.create_player("Host3")
    p2_3 = tester3.create_player("Player2")
    p3_3 = tester3.create_player("Player3")
    p4_3 = tester3.create_player("Player4")

    if tester3.create_game(host3):
        for p in [p2_3, p3_3, p4_3]:
            tester3.join_game(p)
        tester3.players = [host3, p2_3, p3_3, p4_3]

        if tester3.start_game(host3):
            # Get player IDs
            for player in tester3.players:
                info = tester3.get_player_info(player)
                player.player_id = info['id'] if info else player.player_id

            # Start meeting
            if tester3.start_meeting(host3):
                time.sleep(0.5)
                if tester3.start_voting(host3):
                    time.sleep(6)  # Wait for discussion

                    # 2 vote for p2_3, 2 vote for p3_3 (tie)
                    tester3.cast_vote(host3, target_id=p2_3.player_id)
                    tester3.cast_vote(p4_3, target_id=p2_3.player_id)
                    tester3.cast_vote(p2_3, target_id=p3_3.player_id)
                    tester3.cast_vote(p3_3, target_id=p3_3.player_id)

                    time.sleep(1)

                    # Check result - no one eliminated (tie)
                    state = tester3.get_game_state(host3)
                    alive_count = sum(1 for p in state['players'] if p['status'] == 'alive')
                    tester3.assert_test(
                        alive_count == 4,
                        "Tie vote → no elimination (all 4 players still alive)"
                    )

                    tester3.end_meeting(host3)

    # Print summary
    print("\n" + "="*60)
    print("VOTING SCENARIOS SUMMARY")
    print("="*60)
    total_passed = tester.tests_passed + tester2.tests_passed + tester3.tests_passed
    total_failed = tester.tests_failed + tester2.tests_failed + tester3.tests_failed
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print("="*60)


def main():
    """Run the test suite"""
    print("="*60)
    print("🎮 Among Us IRL - Automated Test Suite")
    print("="*60)
    print(f"Target: {BASE_URL}\n")

    tester = GameTester(BASE_URL)

    # === PHASE 1: Lobby Setup ===
    print("\n📍 PHASE 1: Lobby Setup")
    print("-" * 60)

    # Create players
    host = tester.create_player("Alice (Host)")
    player2 = tester.create_player("Bob")
    player3 = tester.create_player("Charlie")
    player4 = tester.create_player("Diana")

    tester.players = [host, player2, player3, player4]

    # Create and join game
    if not tester.create_game(host):
        print("❌ Failed to create game. Exiting.")
        return

    for player in [player2, player3, player4]:
        if not tester.join_game(player):
            print(f"❌ Failed to join as {player.name}. Continuing...")

    # Update settings
    tester.update_settings(host, {
        "num_impostors": 1,
        "meeting_timer_duration": 60,
        "discussion_time": 5,
        "enable_voting": True,
        "anonymous_voting": False
    })

    # === PHASE 2: Game Start ===
    print("\n📍 PHASE 2: Game Start")
    print("-" * 60)

    if not tester.start_game(host):
        print("❌ Failed to start game. Exiting.")
        return

    # Get player info for everyone
    for player in tester.players:
        info = tester.get_player_info(player)
        if info:
            player.role = info.get('role')

    # Print roles
    print("\n👥 Assigned Roles:")
    for player in tester.players:
        print(f"   {player.name}: {player.role or 'Unknown'}")

    # === PHASE 3: Gameplay ===
    print("\n📍 PHASE 3: Gameplay")
    print("-" * 60)

    # Find a crewmate to complete tasks
    crewmate = next((p for p in tester.players if p.role and 'Crewmate' in p.role), None)
    if crewmate:
        info = tester.get_player_info(crewmate)
        if info and info.get('tasks'):
            first_task_id = info['tasks'][0]['id']
            tester.complete_task(crewmate, first_task_id)

    # === PHASE 4: Meeting & Voting ===
    print("\n📍 PHASE 4: Meeting & Voting")
    print("-" * 60)

    # Start meeting
    if tester.start_meeting(host, is_body_report=False):
        time.sleep(0.5)

        # Start voting
        if tester.start_voting(host):
            # Wait for discussion time to end (we set it to 5 seconds)
            time.sleep(6)

            # Everyone votes (skip)
            for player in tester.players:
                tester.cast_vote(player, target_id=None)

            time.sleep(1)

            # End meeting
            tester.end_meeting(host)

    # === PHASE 5: Role Abilities (if applicable) ===
    print("\n📍 PHASE 5: Role Abilities")
    print("-" * 60)

    # Test Captain ability if someone is captain
    captain = next((p for p in tester.players if p.role == 'Captain'), None)
    if captain:
        tester.captain_meeting(captain)
        time.sleep(0.5)
        tester.end_meeting(host)

    # === PHASE 6: Sabotage (if applicable) ===
    print("\n📍 PHASE 6: Sabotage")
    print("-" * 60)

    # Find impostor
    impostor = next((p for p in tester.players if p.role == 'Impostor'), None)
    if impostor:
        # Try to start sabotage (1=Lights)
        if tester.start_sabotage(impostor, 1):
            time.sleep(0.5)
            # Fix it
            tester.fix_sabotage(crewmate or host)

    # === Summary ===
    tester.print_summary()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "voting":
        # Run voting scenarios test
        test_voting_scenarios()
    else:
        # Run basic flow test (default)
        main()
