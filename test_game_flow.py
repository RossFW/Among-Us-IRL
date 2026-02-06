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
BASE_URL = "https://imposter.rossfw.com"
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

    def mark_dead(self, player: Player, target_id: str) -> bool:
        """Test: Mark a player as dead"""
        try:
            response = requests.post(
                f"{self.base_url}/api/players/{target_id}/die",
                params={"session_token": player.session_token}
            )
            self.assert_test(
                response.status_code == 200,
                f"Marked player {target_id[:4]}... as dead"
            )
            return response.status_code == 200
        except Exception as e:
            self.assert_test(False, f"Mark dead (error: {e})")
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


def test_edge_cases():
    """Test edge cases and invalid operations"""
    print("\n" + "="*60)
    print("⚠️  EDGE CASES TEST SUITE")
    print("="*60)

    tester = GameTester(BASE_URL)

    # Test 1: Dead player can't vote
    print("\n📍 TEST: Dead player cannot vote")
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
            # Get player IDs
            for player in tester.players:
                info = tester.get_player_info(player)
                if info:
                    player.player_id = info['id']

            # Kill one player first (player marks themselves as dead)
            if tester.mark_dead(p2, p2.player_id):
                tester.assert_test(True, "Player marked as dead")

                # Start meeting and voting
                if tester.start_meeting(host):
                    time.sleep(0.5)
                    if tester.start_voting(host):
                        time.sleep(6)

                        # Dead player tries to vote (should fail)
                        response = tester.cast_vote(p2, target_id=None)
                        tester.assert_test(
                            not response,
                            "Dead player cannot vote (rejected)"
                        )

                        # Alive players can vote
                        tester.cast_vote(host, target_id=None)
                        tester.cast_vote(p3, target_id=None)
                        tester.cast_vote(p4, target_id=None)

                        time.sleep(1)
                        tester.end_meeting(host)

    # Test 2: Non-host can't change settings
    print("\n📍 TEST: Non-host cannot change settings")
    print("-" * 60)
    tester2 = GameTester(BASE_URL)
    host2 = tester2.create_player("Host2")
    p2_2 = tester2.create_player("Player2")

    if tester2.create_game(host2):
        tester2.join_game(p2_2)
        tester2.players = [host2, p2_2]

        # Non-host tries to change settings (should fail)
        response = tester2.update_settings(p2_2, {"num_impostors": 2})
        tester2.assert_test(
            not response,
            "Non-host cannot change settings (rejected)"
        )

    # Test 3: Task completion after death (ghosts can complete tasks)
    print("\n📍 TEST: Dead player CAN complete tasks (ghost)")
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
            # Find a crewmate with tasks
            for player in tester3.players:
                info = tester3.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    player.player_id = info['id']

            crewmate = next((p for p in tester3.players if p.role and 'Crewmate' in p.role), None)
            if crewmate:
                # Get task
                info = tester3.get_player_info(crewmate)
                if info and info.get('tasks'):
                    task_id = info['tasks'][0]['id']

                    # Kill the crewmate (player marks themselves as dead)
                    tester3.mark_dead(crewmate, crewmate.player_id)
                    time.sleep(0.5)

                    # Ghost tries to complete task (should work!)
                    if tester3.complete_task(crewmate, task_id):
                        tester3.assert_test(
                            True,
                            "Dead player (ghost) CAN complete tasks"
                        )

    # Print summary
    print("\n" + "="*60)
    print("EDGE CASES SUMMARY")
    print("="*60)
    print(f"✅ Passed: {tester.tests_passed + tester2.tests_passed + tester3.tests_passed}")
    print(f"❌ Failed: {tester.tests_failed + tester2.tests_failed + tester3.tests_failed}")
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


def test_slot_based_roles():
    """Test the slot-based role assignment pipeline"""
    print("\n" + "="*60)
    print("🎰 SLOT-BASED ROLE ASSIGNMENT TEST SUITE")
    print("="*60)

    # Test 1: Default settings (1 impostor, 0 neutrals, 0 advanced crew)
    print("\n📍 TEST: Default settings — all crew except 1 impostor")
    print("-" * 60)
    tester = GameTester(BASE_URL)
    host = tester.create_player("Host")
    players = [host]
    for i in range(2, 6):
        players.append(tester.create_player(f"P{i}"))

    if tester.create_game(host):
        for p in players[1:]:
            tester.join_game(p)
        tester.players = players

        if tester.start_game(host):
            roles = {}
            for player in tester.players:
                info = tester.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    roles[player.name] = player.role

            print(f"   Roles: {roles}")
            impostor_count = sum(1 for r in roles.values() if r in ['Impostor', 'Riddler', 'Rampager', 'Cleaner', 'Venter', 'Minion'])
            crew_count = sum(1 for r in roles.values() if r in ['Crewmate', 'Sheriff', 'Engineer', 'Captain', 'Mayor', 'Bounty Hunter', 'Spy', 'Swapper', 'Noise Maker', 'Lookout'])
            tester.assert_test(impostor_count == 1, f"Default: exactly 1 impostor (got {impostor_count})")
            tester.assert_test(crew_count == 4, f"Default: 4 crew (got {crew_count})")

    # Test 2: num_neutrals=1 with jester enabled
    print("\n📍 TEST: 1 neutral slot with jester enabled")
    print("-" * 60)
    tester2 = GameTester(BASE_URL)
    host2 = tester2.create_player("Host")
    players2 = [host2]
    for i in range(2, 7):
        players2.append(tester2.create_player(f"P{i}"))

    if tester2.create_game(host2):
        for p in players2[1:]:
            tester2.join_game(p)
        tester2.players = players2

        tester2.update_settings(host2, {
            "num_neutrals": 1,
            "role_configs": {"jester": {"enabled": True}}
        })

        if tester2.start_game(host2):
            roles2 = {}
            for player in tester2.players:
                info = tester2.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    roles2[player.name] = player.role

            print(f"   Roles: {roles2}")
            has_jester = 'Jester' in roles2.values()
            tester2.assert_test(has_jester, "1 neutral slot + jester enabled → Jester assigned")

    # Test 3: num_advanced_crew=2 with sheriff and engineer enabled
    print("\n📍 TEST: 2 advanced crew slots with sheriff + engineer")
    print("-" * 60)
    tester3 = GameTester(BASE_URL)
    host3 = tester3.create_player("Host")
    players3 = [host3]
    for i in range(2, 8):
        players3.append(tester3.create_player(f"P{i}"))

    if tester3.create_game(host3):
        for p in players3[1:]:
            tester3.join_game(p)
        tester3.players = players3

        tester3.update_settings(host3, {
            "num_advanced_crew": 2,
            "role_configs": {
                "sheriff": {"enabled": True},
                "engineer": {"enabled": True}
            }
        })

        if tester3.start_game(host3):
            roles3 = {}
            for player in tester3.players:
                info = tester3.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    roles3[player.name] = player.role

            print(f"   Roles: {roles3}")
            advanced_crew = sum(1 for r in roles3.values() if r in ['Sheriff', 'Engineer'])
            tester3.assert_test(advanced_crew == 2, f"2 advanced crew slots → 2 advanced crew roles (got {advanced_crew})")

    # Test 4: More slots than enabled roles (should fill with defaults)
    print("\n📍 TEST: 3 impostor slots, only 1 variant enabled → 1 variant + 2 base Impostors")
    print("-" * 60)
    tester4 = GameTester(BASE_URL)
    host4 = tester4.create_player("Host")
    players4 = [host4]
    for i in range(2, 9):
        players4.append(tester4.create_player(f"P{i}"))

    if tester4.create_game(host4):
        for p in players4[1:]:
            tester4.join_game(p)
        tester4.players = players4

        tester4.update_settings(host4, {
            "num_impostors": 3,
            "role_configs": {
                "evil_guesser": {"enabled": True}
            }
        })

        if tester4.start_game(host4):
            roles4 = {}
            for player in tester4.players:
                info = tester4.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    roles4[player.name] = player.role

            print(f"   Roles: {roles4}")
            total_imp = sum(1 for r in roles4.values() if r in ['Impostor', 'Riddler', 'Rampager', 'Cleaner', 'Venter', 'Minion'])
            tester4.assert_test(total_imp == 3, f"3 impostor slots → 3 impostor-aligned (got {total_imp})")
            base_imp = sum(1 for r in roles4.values() if r == 'Impostor')
            tester4.assert_test(base_imp >= 2, f"Only 1 variant enabled → at least 2 base Impostors (got {base_imp})")

    # Test 5: Full pipeline — all 3 categories
    print("\n📍 TEST: Full pipeline — 2 impostors, 1 neutral, 2 crew variants")
    print("-" * 60)
    tester5 = GameTester(BASE_URL)
    host5 = tester5.create_player("Host")
    players5 = [host5]
    for i in range(2, 11):
        players5.append(tester5.create_player(f"P{i}"))

    if tester5.create_game(host5):
        for p in players5[1:]:
            tester5.join_game(p)
        tester5.players = players5

        tester5.update_settings(host5, {
            "num_impostors": 2,
            "num_neutrals": 1,
            "num_advanced_crew": 2,
            "role_configs": {
                "evil_guesser": {"enabled": True},
                "bounty_hunter": {"enabled": True},
                "jester": {"enabled": True},
                "lone_wolf": {"enabled": True},
                "sheriff": {"enabled": True},
                "engineer": {"enabled": True},
                "captain": {"enabled": True}
            }
        })

        if tester5.start_game(host5):
            roles5 = {}
            for player in tester5.players:
                info = tester5.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    roles5[player.name] = player.role

            print(f"   Roles: {roles5}")
            imp_count = sum(1 for r in roles5.values() if r in ['Impostor', 'Riddler', 'Rampager', 'Cleaner', 'Venter', 'Minion'])
            neut_count = sum(1 for r in roles5.values() if r in ['Jester', 'Lone Wolf', 'Vulture', 'Executioner', 'Noise Maker'])
            adv_crew = sum(1 for r in roles5.values() if r in ['Sheriff', 'Engineer', 'Captain', 'Mayor', 'Bounty Hunter', 'Spy', 'Swapper', 'Lookout'])
            base_crew = sum(1 for r in roles5.values() if r == 'Crewmate')
            tester5.assert_test(imp_count == 2, f"2 impostor slots → 2 impostors (got {imp_count})")
            tester5.assert_test(neut_count == 1, f"1 neutral slot → 1 neutral (got {neut_count})")
            tester5.assert_test(adv_crew == 2, f"2 crew slots → 2 advanced crew (got {adv_crew})")
            tester5.assert_test(base_crew == 5, f"Remaining 5 → Crewmate (got {base_crew})")

    # Print summary
    print("\n" + "="*60)
    print("SLOT-BASED ROLE ASSIGNMENT SUMMARY")
    print("="*60)
    total_passed = sum(t.tests_passed for t in [tester, tester2, tester3, tester4, tester5])
    total_failed = sum(t.tests_failed for t in [tester, tester2, tester3, tester4, tester5])
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print("="*60)


def test_executioner():
    """Test Executioner role mechanics"""
    print("\n" + "="*60)
    print("⚖️  EXECUTIONER TEST SUITE")
    print("="*60)

    # Test 1: Executioner gets a target on game start
    print("\n📍 TEST: Executioner target assignment")
    print("-" * 60)
    tester = GameTester(BASE_URL)
    host = tester.create_player("Host")
    players = [host]
    for i in range(2, 7):
        players.append(tester.create_player(f"P{i}"))

    if tester.create_game(host):
        for p in players[1:]:
            tester.join_game(p)
        tester.players = players

        tester.update_settings(host, {
            "num_neutrals": 1,
            "role_configs": {"executioner": {"enabled": True}}
        })

        if tester.start_game(host):
            executioner = None
            for player in tester.players:
                info = tester.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    if player.role == 'Executioner':
                        executioner = player
                        target = info.get('executioner_target')
                        tester.assert_test(
                            target is not None and 'name' in target,
                            f"Executioner has a target: {target.get('name') if target else 'None'}"
                        )
                        # Verify target is crew-aligned (not impostor)
                        target_id = target['id'] if target else None
                        target_player = next((p for p in tester.players if p.player_id == target_id), None)
                        if target_player:
                            target_info = tester.get_player_info(target_player)
                            target_role = target_info.get('role') if target_info else None
                            crew_roles = ['Crewmate', 'Sheriff', 'Engineer', 'Captain', 'Mayor', 'Bounty Hunter', 'Spy', 'Swapper', 'Noise Maker', 'Lookout']
                            tester.assert_test(
                                target_role in crew_roles,
                                f"Executioner target is crew-aligned: {target_role}"
                            )

            if not executioner:
                tester.assert_test(False, "No Executioner assigned (needed for test)")

    # Test 2: Executioner wins when target is voted out
    print("\n📍 TEST: Executioner wins when target voted out (and Exe voted for target)")
    print("-" * 60)
    tester2 = GameTester(BASE_URL)
    host2 = tester2.create_player("Host")
    players2 = [host2]
    for i in range(2, 7):
        players2.append(tester2.create_player(f"P{i}"))

    if tester2.create_game(host2):
        for p in players2[1:]:
            tester2.join_game(p)
        tester2.players = players2

        tester2.update_settings(host2, {
            "num_neutrals": 1,
            "role_configs": {"executioner": {"enabled": True}}
        })

        if tester2.start_game(host2):
            executioner2 = None
            exec_target_id = None
            for player in tester2.players:
                info = tester2.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    player.player_id = info['id']
                    if player.role == 'Executioner':
                        executioner2 = player
                        target = info.get('executioner_target')
                        exec_target_id = target['id'] if target else None

            if executioner2 and exec_target_id:
                # Start meeting
                non_exec_alive = [p for p in tester2.players if p.player_id != executioner2.player_id and p.role != 'Executioner']
                caller = non_exec_alive[0] if non_exec_alive else host2

                if tester2.start_meeting(caller):
                    time.sleep(0.5)
                    if tester2.start_voting(caller):
                        time.sleep(6)
                        # Everyone votes for the executioner's target
                        for player in tester2.players:
                            tester2.cast_vote(player, target_id=exec_target_id)

                        time.sleep(1)

                        # Check: game should end with Executioner win
                        state = tester2.get_game_state(host2)
                        tester2.assert_test(
                            state and state.get('state') == 'ended',
                            "Game ended after executioner's target voted out"
                        )
                        tester2.assert_test(
                            state and state.get('winner') == 'Executioner',
                            f"Winner is Executioner (got: {state.get('winner') if state else 'N/A'})"
                        )
            else:
                tester2.assert_test(False, "No Executioner or no target found for voting test")

    # Test 3: Executioner fallback to Jester when target dies outside vote
    print("\n📍 TEST: Executioner becomes Jester when target dies non-vote")
    print("-" * 60)
    tester3 = GameTester(BASE_URL)
    host3 = tester3.create_player("Host")
    players3 = [host3]
    for i in range(2, 7):
        players3.append(tester3.create_player(f"P{i}"))

    if tester3.create_game(host3):
        for p in players3[1:]:
            tester3.join_game(p)
        tester3.players = players3

        tester3.update_settings(host3, {
            "num_neutrals": 1,
            "role_configs": {"executioner": {"enabled": True}}
        })

        if tester3.start_game(host3):
            executioner3 = None
            exec_target_id3 = None
            target_player3 = None
            for player in tester3.players:
                info = tester3.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    player.player_id = info['id']
                    if player.role == 'Executioner':
                        executioner3 = player
                        target = info.get('executioner_target')
                        exec_target_id3 = target['id'] if target else None

            if executioner3 and exec_target_id3:
                target_player3 = next((p for p in tester3.players if p.player_id == exec_target_id3), None)

                if target_player3:
                    # Kill the target via mark_dead (non-vote death)
                    tester3.mark_dead(target_player3, target_player3.player_id)
                    time.sleep(0.5)

                    # Check: Executioner should now be Jester
                    exec_info = tester3.get_player_info(executioner3)
                    new_role = exec_info.get('role') if exec_info else None
                    tester3.assert_test(
                        new_role == 'Jester',
                        f"Executioner became Jester after target died (role: {new_role})"
                    )
            else:
                tester3.assert_test(False, "No Executioner or target for fallback test")

    # Print summary
    print("\n" + "="*60)
    print("EXECUTIONER SUMMARY")
    print("="*60)
    total_passed = sum(t.tests_passed for t in [tester, tester2, tester3])
    total_failed = sum(t.tests_failed for t in [tester, tester2, tester3])
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print("="*60)


def test_lookout():
    """Test Lookout role mechanics"""
    print("\n" + "="*60)
    print("👁️  LOOKOUT TEST SUITE")
    print("="*60)

    # Test 1: Lookout can select a player to watch
    print("\n📍 TEST: Lookout selection")
    print("-" * 60)
    tester = GameTester(BASE_URL)
    host = tester.create_player("Host")
    players = [host]
    for i in range(2, 7):
        players.append(tester.create_player(f"P{i}"))

    if tester.create_game(host):
        for p in players[1:]:
            tester.join_game(p)
        tester.players = players

        tester.update_settings(host, {
            "num_advanced_crew": 1,
            "role_configs": {"lookout": {"enabled": True}}
        })

        if tester.start_game(host):
            lookout = None
            for player in tester.players:
                info = tester.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    player.player_id = info['id']
                    if player.role == 'Lookout':
                        lookout = player
                        selectable = info.get('lookout_selectable', [])
                        tester.assert_test(
                            len(selectable) > 0,
                            f"Lookout has selectable players ({len(selectable)} available)"
                        )

            if lookout:
                # Select a player to watch
                other = next((p for p in tester.players if p.player_id != lookout.player_id and p.role != 'Impostor'), None)
                if other:
                    try:
                        response = requests.post(
                            f"{tester.base_url}/api/games/{tester.game_code}/ability/lookout-select",
                            params={"session_token": lookout.session_token, "target_player_id": other.player_id}
                        )
                        tester.assert_test(
                            response.status_code == 200,
                            f"Lookout selected {other.name} to watch"
                        )
                    except Exception as e:
                        tester.assert_test(False, f"Lookout select failed: {e}")

                    # Verify via player info
                    info = tester.get_player_info(lookout)
                    if info:
                        lookout_target = info.get('lookout_target')
                        tester.assert_test(
                            lookout_target and lookout_target.get('id') == other.player_id,
                            f"Lookout target confirmed as {other.name}"
                        )

                # Test: Lookout cannot watch themselves
                try:
                    response = requests.post(
                        f"{tester.base_url}/api/games/{tester.game_code}/ability/lookout-select",
                        params={"session_token": lookout.session_token, "target_player_id": lookout.player_id}
                    )
                    tester.assert_test(
                        response.status_code == 400,
                        "Lookout cannot watch themselves (rejected)"
                    )
                except Exception as e:
                    tester.assert_test(False, f"Lookout self-watch test failed: {e}")
            else:
                tester.assert_test(False, "No Lookout assigned")

    # Test 2: Lookout selection constraint (only players alive at last meeting)
    print("\n📍 TEST: Lookout selection constraint after meeting")
    print("-" * 60)
    tester2 = GameTester(BASE_URL)
    host2 = tester2.create_player("Host")
    players2 = [host2]
    for i in range(2, 7):
        players2.append(tester2.create_player(f"P{i}"))

    if tester2.create_game(host2):
        for p in players2[1:]:
            tester2.join_game(p)
        tester2.players = players2

        tester2.update_settings(host2, {
            "num_advanced_crew": 1,
            "role_configs": {"lookout": {"enabled": True}},
            "discussion_time": 1
        })

        if tester2.start_game(host2):
            lookout2 = None
            for player in tester2.players:
                info = tester2.get_player_info(player)
                if info:
                    player.role = info.get('role')
                    player.player_id = info['id']
                    if player.role == 'Lookout':
                        lookout2 = player

            if lookout2:
                # Kill a player
                victim = next((p for p in tester2.players if p.player_id != lookout2.player_id and p.role not in ['Impostor', 'Lookout']), None)
                if victim:
                    tester2.mark_dead(victim, victim.player_id)
                    time.sleep(0.3)

                # Run a meeting and end it to snapshot alive players
                alive_caller = next((p for p in tester2.players if p.role not in ['Lookout'] and p.player_id != (victim.player_id if victim else '')), None)
                if alive_caller:
                    if tester2.start_meeting(alive_caller):
                        time.sleep(0.5)
                        if tester2.start_voting(alive_caller):
                            time.sleep(2)
                            # Everyone skips
                            for p in tester2.players:
                                info_p = tester2.get_player_info(p)
                                if info_p and info_p.get('status') == 'alive':
                                    tester2.cast_vote(p, target_id=None)
                            time.sleep(1)
                            tester2.end_meeting(alive_caller)
                            time.sleep(0.3)

                # After meeting, lookout selectable should NOT include dead player
                info2 = tester2.get_player_info(lookout2)
                if info2:
                    selectable2 = info2.get('lookout_selectable', [])
                    dead_in_selectable = any(s['id'] == victim.player_id for s in selectable2) if victim else False
                    tester2.assert_test(
                        not dead_in_selectable,
                        "Dead player not in Lookout selectable list after meeting"
                    )
            else:
                tester2.assert_test(False, "No Lookout assigned for constraint test")

    # Print summary
    print("\n" + "="*60)
    print("LOOKOUT SUMMARY")
    print("="*60)
    total_passed = tester.tests_passed + tester2.tests_passed
    total_failed = tester.tests_failed + tester2.tests_failed
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")
    print("="*60)


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
        elif test_type == "edge":
            test_edge_cases()
        elif test_type == "slots":
            test_slot_based_roles()
        elif test_type == "executioner":
            test_executioner()
        elif test_type == "lookout":
            test_lookout()
        elif test_type == "new":
            test_slot_based_roles()
            print("\n")
            test_executioner()
            print("\n")
            test_lookout()
        elif test_type == "all":
            main()
            print("\n")
            test_voting_scenarios()
            print("\n")
            test_role_abilities()
            print("\n")
            test_sabotage_scenarios()
            print("\n")
            test_edge_cases()
            print("\n")
            test_slot_based_roles()
            print("\n")
            test_executioner()
            print("\n")
            test_lookout()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python test_game_flow.py [voting|abilities|sabotage|edge|slots|executioner|lookout|new|all]")
    else:
        # Run basic flow test (default)
        main()
