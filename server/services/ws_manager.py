"""WebSocket connection manager for real-time game updates."""

from fastapi import WebSocket
from typing import Optional
import json


class ConnectionManager:
    """Manages WebSocket connections grouped by game code."""

    def __init__(self):
        # game_code -> {player_id -> WebSocket}
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, game_code: str, player_id: str, websocket: WebSocket):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if game_code not in self.active_connections:
            self.active_connections[game_code] = {}
        self.active_connections[game_code][player_id] = websocket

    def disconnect(self, game_code: str, player_id: str):
        """Remove a WebSocket connection."""
        if game_code in self.active_connections:
            self.active_connections[game_code].pop(player_id, None)
            if not self.active_connections[game_code]:
                del self.active_connections[game_code]

    async def broadcast_to_game(self, game_code: str, message: dict, exclude_player: Optional[str] = None):
        """Send message to all players in a game."""
        if game_code not in self.active_connections:
            return

        disconnected = []
        for player_id, ws in self.active_connections[game_code].items():
            if exclude_player and player_id == exclude_player:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(player_id)

        # Clean up disconnected
        for player_id in disconnected:
            self.disconnect(game_code, player_id)

    async def send_to_player(self, game_code: str, player_id: str, message: dict):
        """Send message to a specific player."""
        if game_code not in self.active_connections:
            return False

        ws = self.active_connections[game_code].get(player_id)
        if ws:
            try:
                await ws.send_json(message)
                return True
            except Exception:
                self.disconnect(game_code, player_id)
        return False

    def get_connected_players(self, game_code: str) -> set[str]:
        """Get set of connected player IDs for a game."""
        if game_code not in self.active_connections:
            return set()
        return set(self.active_connections[game_code].keys())


# Global manager instance
ws_manager = ConnectionManager()
