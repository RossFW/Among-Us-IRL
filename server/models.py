"""Data models and enums for Among Us IRL."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import random
import string


class GameState(str, Enum):
    LOBBY = "lobby"
    PLAYING = "playing"
    MEETING = "meeting"
    ENDED = "ended"


class Role(str, Enum):
    CREWMATE = "Crewmate"
    IMPOSTOR = "Impostor"
    JESTER = "Jester"
    LONE_WOLF = "Lone Wolf"
    MINION = "Minion"


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class PlayerStatus(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"


# Default tasks from the original Discord bot
DEFAULT_TASKS = [
    "Books", "Bottle flip", "Cards", "Clean vent", "Code", "Coins",
    "Colors", "Cup stack", "Dice", "Files", "Folding", "Leaves",
    "Scooter", "Trashketball", "Water pong", "Wires"
]


def generate_game_code() -> str:
    """Generate a 4-letter game code."""
    return ''.join(random.choices(string.ascii_uppercase, k=4))


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())


def generate_session_token() -> str:
    """Generate a secure session token."""
    return str(uuid.uuid4())


# Pydantic models for API requests/responses

class TaskModel(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    status: TaskStatus = TaskStatus.PENDING
    is_fake: bool = False


class PlayerModel(BaseModel):
    id: str = Field(default_factory=generate_id)
    name: str
    session_token: str = Field(default_factory=generate_session_token)
    role: Optional[Role] = None
    status: PlayerStatus = PlayerStatus.ALIVE
    tasks: list[TaskModel] = Field(default_factory=list)
    is_host: bool = False
    connected: bool = True


class GameSettings(BaseModel):
    tasks_per_player: int = 5
    num_impostors: int = 2
    enable_jester: bool = False
    enable_lone_wolf: bool = False
    enable_minion: bool = False


class GameModel(BaseModel):
    id: str = Field(default_factory=generate_id)
    code: str = Field(default_factory=generate_game_code)
    state: GameState = GameState.LOBBY
    settings: GameSettings = Field(default_factory=GameSettings)
    players: dict[str, PlayerModel] = Field(default_factory=dict)
    available_tasks: list[str] = Field(default_factory=lambda: DEFAULT_TASKS.copy())
    crewmate_task_total: int = 0
    winner: Optional[str] = None

    def get_task_completion_percentage(self) -> float:
        """Calculate task completion percentage."""
        if self.crewmate_task_total == 0:
            return 0.0
        completed = sum(
            1 for p in self.players.values()
            if p.role == Role.CREWMATE
            for t in p.tasks
            if t.status == TaskStatus.COMPLETED
        )
        return round((completed / self.crewmate_task_total) * 100, 1)

    def get_alive_players(self) -> list[PlayerModel]:
        """Get list of alive players."""
        return [p for p in self.players.values() if p.status == PlayerStatus.ALIVE]

    def get_dead_players(self) -> list[PlayerModel]:
        """Get list of dead players."""
        return [p for p in self.players.values() if p.status == PlayerStatus.DEAD]

    def get_player_by_session(self, session_token: str) -> Optional[PlayerModel]:
        """Find player by session token."""
        for player in self.players.values():
            if player.session_token == session_token:
                return player
        return None


# API request/response models

class CreateGameRequest(BaseModel):
    player_name: str


class JoinGameRequest(BaseModel):
    player_name: str


class UpdateSettingsRequest(BaseModel):
    tasks_per_player: Optional[int] = None
    num_impostors: Optional[int] = None
    enable_jester: Optional[bool] = None
    enable_lone_wolf: Optional[bool] = None
    enable_minion: Optional[bool] = None


class AddTaskRequest(BaseModel):
    task_name: str


class GameResponse(BaseModel):
    code: str
    state: GameState
    settings: GameSettings
    players: list[dict]
    available_tasks: list[str]
    task_percentage: float


class PlayerResponse(BaseModel):
    id: str
    name: str
    session_token: str
    is_host: bool
