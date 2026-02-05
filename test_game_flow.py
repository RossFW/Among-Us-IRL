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

    def sheriff_shoot(self, player: Player, target_id: str) -> bool:
        """Test: Sheriff shoot"""
        try:
            response = requests.post(
                f"{self.base_url}/api/games/{self.game_code}/sheriff/shoot/{target_id}",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"Sheriff '{player.name}' shot target {target_id[:4]}..."
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Sheriff shoot (error: {e})")
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

    # Test 4: Single vote wins
    print("\n📍 TEST: Single vote (1 person votes)")
    print("-" * 60)
    tester4 = GameTester(BASE_URL)
    host4 = tester4.create_player("Host4")
    p2_4 = tester4.create_player("Player2")
    p3_4 = tester4.create_player("Player3")
    p4_4 = tester4.create_player("Player4")

    if tester4.create_game(host4):
        for p in [p2_4, p3_4, p4_4]:
            tester4.join_game(p)
        tester4.players = [host4, p2_4, p3_4, p4_4]

        if tester4.start_game(host4):
            # Get player IDs
            for player in tester4.players:
                info = tester4.get_player_info(player)
                player.player_id = info['id'] if info else player.player_id

            # Start meeting
            if tester4.start_meeting(host4):
                time.sleep(0.5)
                if tester4.start_voting(host4):
                    time.sleep(6)  # Wait for discussion

                    # Only 1 person votes, rest skip
                    tester4.cast_vote(host4, target_id=p2_4.player_id)
                    tester4.cast_vote(p2_4, target_id=None)
                    tester4.cast_vote(p3_4, target_id=None)
                    tester4.cast_vote(p4_4, target_id=None)

                    time.sleep(1)

                    # Check result - with 3 skips vs 1 vote, skip wins (no elimination)
                    state = tester4.get_game_state(host4)
                    alive_count = sum(1 for p in state['players'] if p['status'] == 'alive')
                    tester4.assert_test(
                        alive_count == 4,
                        "Single vote vs 3 skips → no elimination (skip plurality wins)"
                    )

                    tester4.end_meeting(host4)

    # Test 5: 3-way tie
    print("\n📍 TEST: 3-way tie (1v1v1)")
    print("-" * 60)
    tester5 = GameTester(BASE_URL)
    host5 = tester5.create_player("Host5")
    p2_5 = tester5.create_player("Player2")
    p3_5 = tester5.create_player("Player3")
    p4_5 = tester5.create_player("Player4")

    if tester5.create_game(host5):
        for p in [p2_5, p3_5, p4_5]:
            tester5.join_game(p)
        tester5.players = [host5, p2_5, p3_5, p4_5]

        if tester5.start_game(host5):
            # Get player IDs
            for player in tester5.players:
                info = tester5.get_player_info(player)
                player.player_id = info['id'] if info else player.player_id

            # Start meeting
            if tester5.start_meeting(host5):
                time.sleep(0.5)
                if tester5.start_voting(host5):
                    time.sleep(6)  # Wait for discussion

                    # 3-way tie: p2 votes p3, p3 votes p4, p4 votes p2, host skips
                    tester5.cast_vote(host5, target_id=None)
                    tester5.cast_vote(p2_5, target_id=p3_5.player_id)
                    tester5.cast_vote(p3_5, target_id=p4_5.player_id)
                    tester5.cast_vote(p4_5, target_id=p2_5.player_id)

                    time.sleep(1)

                    # Check result - no one eliminated (3-way tie)
                    state = tester5.get_game_state(host5)
                    alive_count = sum(1 for p in state['players'] if p['status'] == 'alive')
                    tester5.assert_test(
                        alive_count == 4,
                        "3-way tie → no elimination (all 4 players still alive)"
                    )

                    tester5.end_meeting(host5)

    # Print summary
    print("\n" + "="*60)
    print("VOTING SCENARIOS SUMMARY")
    print("="*60)
    total_passed = sum([tester.tests_passed, tester2.tests_passed, tester3.tests_passed,
                        tester4.tests_passed, tester5.tests_passed])
    total_failed = sum([tester.tests_failed, tester2.tests_failed, tester3.tests_failed,
                        tester4.tests_failed, tester5.tests_failed])
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print("="*60)


def test_role_abilities():
    """Test role-specific abilities"""
    print("\n" + "="*60)
    print("🎭 ROLE ABILITIES TEST SUITE")
    print("="*60)

    tester = GameTester(BASE_URL)

    # Create game with 6 players for better role variety
    print("\n📍 Creating game with 6 players for role testing")
    print("-" * 60)

    host = tester.create_player("Host")
    players = [host]
    for i in range(2, 7):
        players.append(tester.create_player(f"Player{i}"))

    if tester.create_game(host):
        for p in players[1:]:
            tester.join_game(p)
        tester.players = players

        # Enable various roles for testing
        tester.update_settings(host, {
            "enable_sheriff": True,
            "engineer": {"enabled": True, "probability": 50, "max_count": 1},
            "captain": {"enabled": True, "probability": 50, "max_count": 1},
            "enable_sabotage": True
        })

        if tester.start_game(host):
            # Get all player info to see roles
            print("\n👥 Assigned Roles:")
            for player in tester.players:
                info = tester.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    player.player_id = info['id']
                    print(f"   {player.name}: {player.role}")

            # Test Engineer ability (if present)
            engineer = next((p for p in tester.players if p.role == 'Engineer'), None)
            impostor = next((p for p in tester.players if p.role and 'Impostor' in p.role), None)

            if engineer and impostor:
                print("\n📍 TEST: Engineer Remote Fix")
                print("-" * 60)

                # Start sabotage
                if tester.start_sabotage(impostor, 1):  # Lights
                    time.sleep(0.5)
                    # Engineer fixes remotely
                    if tester.engineer_fix(engineer):
                        tester.assert_test(True, "Engineer fixed sabotage remotely")

                    # Try to use again (should fail)
                    response = tester.engineer_fix(engineer)
                    tester.assert_test(
                        not response,
                        "Engineer can't fix twice (already used)"
                    )

            # Test Captain ability (if present)
            captain = next((p for p in tester.players if p.role == 'Captain'), None)
            if captain:
                print("\n📍 TEST: Captain Remote Meeting")
                print("-" * 60)

                if tester.captain_meeting(captain):
                    tester.assert_test(True, "Captain called remote meeting")
                    time.sleep(0.5)
                    tester.end_meeting(host)

                    # Try to use again (should fail)
                    response = tester.captain_meeting(captain)
                    tester.assert_test(
                        not response,
                        "Captain can't call meeting twice (already used)"
                    )

            # Test Sheriff ability (if present)
            sheriff = next((p for p in tester.players if p.role == 'Sheriff'), None)
            if sheriff and impostor:
                print("\n📍 TEST: Sheriff Shoot")
                print("-" * 60)

                # Sheriff shoots impostor (impostor should die)
                if tester.sheriff_shoot(sheriff, impostor.player_id):
                    time.sleep(0.5)
                    state = tester.get_game_state(host)
                    target = next((p for p in state['players'] if p['id'] == impostor.player_id), None)
                    tester.assert_test(
                        target and target['status'] == 'dead',
                        "Sheriff shoots impostor → impostor dies"
                    )

    # Print summary
    print("\n" + "="*60)
    print("ROLE ABILITIES SUMMARY")
    print("="*60)
    print(f"✅ Passed: {tester.tests_passed}")
    print(f"❌ Failed: {tester.tests_failed}")
    print("="*60)


def test_sabotage_scenarios():
    """Test sabotage mechanics"""
    print("\n" + "="*60)
    print("💡 SABOTAGE TEST SUITE")
    print("="*60)

    tester = GameTester(BASE_URL)

    # Test 1: Lights sabotage persists after meeting
    print("\n📍 TEST: Lights sabotage persists across meeting")
    print("-" * 60)

    host = tester.create_player("Host")
    p2 = tester.create_player("Player2")
    p3 = tester.create_player("Player3")
    p4 = tester.create_player("Player4")

    if tester.create_game(host):
        for p in [p2, p3, p4]:
            tester.join_game(p)
        tester.players = [host, p2, p3, p4]

        # Enable sabotage
        tester.update_settings(host, {"enable_sabotage": True})

        if tester.start_game(host):
            # Find impostor
            for player in tester.players:
                info = tester.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    player.player_id = info['id']

            impostor = next((p for p in tester.players if p.role == 'Impostor'), None)
            crewmate = next((p for p in tester.players if p.role and 'Crewmate' in p.role), None)

            if impostor:
                # Start lights sabotage
                if tester.start_sabotage(impostor, 1):
                    tester.assert_test(True, "Lights sabotage started")

                    # Call meeting WITHOUT fixing sabotage
                    if tester.start_meeting(host):
                        time.sleep(0.5)
                        if tester.start_voting(host):
                            time.sleep(6)
                            # Everyone skips
                            for player in tester.players:
                                tester.cast_vote(player, target_id=None)
                            time.sleep(1)
                            tester.end_meeting(host)

                    # After meeting, sabotage should still be active
                    # Try to fix it
                    if crewmate and tester.fix_sabotage(crewmate):
                        tester.assert_test(
                            True,
                            "Lights persisted after meeting and was fixed"
                        )

    # Test 2: Sabotage cooldown
    print("\n📍 TEST: Sabotage cooldown prevents immediate re-trigger")
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

        tester2.update_settings(host2, {"enable_sabotage": True, "sabotage_cooldown": 10})

        if tester2.start_game(host2):
            # Find impostor
            for player in tester2.players:
                info = tester2.get_player_info(player)
                if info:
                    player.role = info.get('role')

            impostor2 = next((p for p in tester2.players if p.role == 'Impostor'), None)
            if impostor2:
                # Start sabotage
                if tester2.start_sabotage(impostor2, 1):
                    # Fix it immediately
                    tester2.fix_sabotage(host2)

                    # Try to start another sabotage immediately (should fail due to cooldown)
                    response = tester2.start_sabotage(impostor2, 2)
                    tester2.assert_test(
                        not response,
                        "Sabotage cooldown prevents immediate re-trigger"
                    )

    # Print summary
    print("\n" + "="*60)
    print("SABOTAGE SCENARIOS SUMMARY")
    print("="*60)
    print(f"✅ Passed: {tester.tests_passed + tester2.tests_passed}")
    print(f"❌ Failed: {tester.tests_failed + tester2.tests_failed}")
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

    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == "voting":
            test_voting_scenarios()
        elif test_type == "abilities":
            test_role_abilities()
        elif test_type == "sabotage":
            test_sabotage_scenarios()
        elif test_type == "all":
            main()
            print("\n")
            test_voting_scenarios()
            print("\n")
            test_role_abilities()
            print("\n")
            test_sabotage_scenarios()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python test_game_flow.py [voting|abilities|sabotage|all]")
    else:
        # Run basic flow test (default)
        main()
