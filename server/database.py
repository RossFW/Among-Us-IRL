"""In-memory game storage with optional SQLite persistence."""

from typing import Optional
from .models import GameModel, PlayerModel, generate_game_code


class GameStore:
    """In-memory store for active games."""

    def __init__(self):
        self.games: dict[str, GameModel] = {}  # code -> GameModel

    def create_game(self, host_name: str) -> tuple[GameModel, PlayerModel]:
        """Create a new game and return the game and host player."""
        # Generate unique code
        code = generate_game_code()
        while code in self.games:
            code = generate_game_code()

        # Create game
        game = GameModel(code=code)

        # Create host player
        host = PlayerModel(name=host_name, is_host=True)
        game.players[host.id] = host

        # Store game
        self.games[code] = game

        return game, host

    def get_game(self, code: str) -> Optional[GameModel]:
        """Get game by code."""
        return self.games.get(code.upper())

    def join_game(self, code: str, player_name: str) -> Optional[tuple[GameModel, PlayerModel]]:
        """Join an existing game."""
        game = self.get_game(code)
        if not game:
            return None

        # Create player
        player = PlayerModel(name=player_name)
        game.players[player.id] = player

        return game, player

    def get_player_by_session(self, session_token: str) -> Optional[tuple[GameModel, PlayerModel]]:
        """Find a player by session token across all games."""
        for game in self.games.values():
            player = game.get_player_by_session(session_token)
            if player:
                return game, player
        return None

    def delete_game(self, code: str) -> bool:
        """Delete a game."""
        if code in self.games:
            del self.games[code]
            return True
        return False

    def cleanup_empty_games(self):
        """Remove games with no connected players."""
        empty_codes = [
            code for code, game in self.games.items()
            if not any(p.connected for p in game.players.values())
        ]
        for code in empty_codes:
            del self.games[code]


# Global store instance
game_store = GameStore()
