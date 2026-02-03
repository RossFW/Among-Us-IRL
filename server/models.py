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


class RoleCategory(str, Enum):
    """Category for win condition grouping."""
    CREW = "crew"
    IMPOSTOR = "impostor"
    NEUTRAL = "neutral"


class Role(str, Enum):
    # Base roles
    CREWMATE = "Crewmate"
    IMPOSTOR = "Impostor"

    # Existing special roles
    JESTER = "Jester"
    LONE_WOLF = "Lone Wolf"
    MINION = "Minion"
    SHERIFF = "Sheriff"

    # New Crewmate variants
    ENGINEER = "Engineer"      # Fix ONE sabotage remotely per game
    CAPTAIN = "Captain"        # Extra remote meeting button (additional to normal)
    MAYOR = "Mayor"            # Vote counts twice
    NICE_GUESSER = "Nice Guesser"  # Quick-guess a player's role during voting
    SPY = "Spy"                # Appears as impostor to impostors
    SWAPPER = "Swapper"        # Swap votes between two players

    # New Impostor variants
    EVIL_GUESSER = "Evil Guesser"  # Same as Nice Guesser but for impostors
    BOUNTY_HUNTER = "Bounty Hunter"  # Shorter cooldown for target, longer for others
    CLEANER = "Cleaner"        # Can "clean" bodies (drag them elsewhere)

    # New Neutral roles
    VULTURE = "Vulture"        # "Eat" X corpses to win
    NOISE_MAKER = "Noise Maker"  # When killed, select who "found" them


# Map roles to their category for win conditions
ROLE_CATEGORIES = {
    Role.CREWMATE: RoleCategory.CREW,
    Role.SHERIFF: RoleCategory.CREW,
    Role.ENGINEER: RoleCategory.CREW,
    Role.CAPTAIN: RoleCategory.CREW,
    Role.MAYOR: RoleCategory.CREW,
    Role.NICE_GUESSER: RoleCategory.CREW,
    Role.SPY: RoleCategory.CREW,
    Role.SWAPPER: RoleCategory.CREW,
    Role.IMPOSTOR: RoleCategory.IMPOSTOR,
    Role.EVIL_GUESSER: RoleCategory.IMPOSTOR,
    Role.BOUNTY_HUNTER: RoleCategory.IMPOSTOR,
    Role.CLEANER: RoleCategory.IMPOSTOR,
    Role.MINION: RoleCategory.IMPOSTOR,  # Wins with impostors
    Role.JESTER: RoleCategory.NEUTRAL,
    Role.LONE_WOLF: RoleCategory.NEUTRAL,
    Role.VULTURE: RoleCategory.NEUTRAL,
    Role.NOISE_MAKER: RoleCategory.NEUTRAL,
}


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class PlayerStatus(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"


class SabotageType(str, Enum):
    LIGHTS = "lights"      # No timer, persists after meeting
    REACTOR = "reactor"    # Timer countdown, needs 2 people to hold simultaneously
    O2 = "o2"              # Timer countdown, needs 2 switches collectively
    COMMS = "comms"        # Placeholder for future


class SabotageState(str, Enum):
    NONE = "none"
    ACTIVE = "active"
    RESOLVED = "resolved"


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

    # Role-specific state fields
    engineer_fix_used: bool = False           # Engineer: has used remote fix
    captain_meeting_used: bool = False        # Captain: has used extra meeting
    guesser_used_this_meeting: bool = False   # Guesser: has guessed this meeting
    swapper_targets: Optional[tuple[str, str]] = None  # Swapper: two player IDs to swap votes
    vulture_bodies_eaten: int = 0             # Vulture: corpses consumed
    bounty_target_id: Optional[str] = None    # Bounty Hunter: current target player ID
    noise_maker_target_id: Optional[str] = None  # Noise Maker: who will "find" them


class RoleConfig(BaseModel):
    """Configuration for probability-based role selection."""
    enabled: bool = False
    probability: int = 100  # 0-100% chance when enabled
    max_count: int = 1      # Maximum players with this role


class GameSettings(BaseModel):
    tasks_per_player: int = 5
    num_impostors: int = 2
    # Legacy role toggles (kept for backwards compatibility)
    enable_jester: bool = False
    enable_lone_wolf: bool = False
    enable_minion: bool = False
    enable_sheriff: bool = False
    # New probability-based role configs
    role_configs: dict[str, RoleConfig] = Field(default_factory=lambda: {
        # Crewmate variants
        "engineer": RoleConfig(),
        "captain": RoleConfig(),
        "mayor": RoleConfig(),
        "nice_guesser": RoleConfig(),
        "spy": RoleConfig(),
        "swapper": RoleConfig(),
        # Impostor variants
        "evil_guesser": RoleConfig(),
        "bounty_hunter": RoleConfig(),
        "cleaner": RoleConfig(),
        # Neutral roles
        "vulture": RoleConfig(),
        "noise_maker": RoleConfig(),
    })
    # Per-character cooldown settings (in seconds)
    kill_cooldown: int = 45  # Legacy, kept for backwards compat
    impostor_kill_cooldown: int = 45
    sheriff_shoot_cooldown: int = 45
    lone_wolf_kill_cooldown: int = 45
    enable_impostor_timer: bool = True
    enable_sheriff_timer: bool = True
    enable_lone_wolf_timer: bool = True
    # Vibration settings (disabled by default - not reliable on all devices)
    vibrate_game_start: bool = False
    vibrate_meeting: bool = False
    vibrate_cooldown: bool = False
    # Meeting cooldown
    meeting_cooldown: int = 30  # Seconds between meetings
    # Sabotage settings
    enable_sabotage: bool = False
    sabotage_cooldown: int = 90  # Global cooldown between sabotages
    # Sabotage 1: Lights
    sabotage_1_enabled: bool = True
    sabotage_1_name: str = "Lights"
    sabotage_1_type: str = "lights"
    sabotage_1_timer: int = 0  # 0 = no countdown
    # Sabotage 2: Reactor
    sabotage_2_enabled: bool = True
    sabotage_2_name: str = "Reactor"
    sabotage_2_type: str = "reactor"
    sabotage_2_timer: int = 45  # Countdown seconds
    # Sabotage 3: O2
    sabotage_3_enabled: bool = True
    sabotage_3_name: str = "O2"
    sabotage_3_type: str = "o2"
    sabotage_3_timer: int = 45
    # Sabotage 4: Placeholder
    sabotage_4_enabled: bool = False
    sabotage_4_name: str = "Comms"
    sabotage_4_type: str = "lights"
    sabotage_4_timer: int = 0
    # Meeting Timer & Voting settings
    meeting_timer_duration: int = 120  # seconds, default 2 minutes
    meeting_warning_time: int = 30     # seconds before end to play warning sound
    enable_voting: bool = True         # Enable in-app voting
    anonymous_voting: bool = False     # If False, show who voted for whom
    discussion_time: int = 5           # seconds of discussion before voting enabled (0 to disable)


class ActiveSabotage(BaseModel):
    """Represents an active sabotage in progress."""
    index: int  # Which sabotage (1-4)
    type: str  # lights, reactor, o2
    name: str
    timer: int  # 0 for no timer
    started_at: float  # timestamp
    started_by: str  # player_id
    # For reactor: need 2 people holding simultaneously
    reactor_holders: list[str] = []  # player_ids currently holding
    # For O2: need 2 switches
    o2_switches: int = 0  # count of switches flipped


class VoteType(str, Enum):
    PLAYER = "player"  # Vote to eliminate a player
    SKIP = "skip"      # Skip voting


class Vote(BaseModel):
    """A single vote cast during a meeting."""
    voter_id: str
    target_id: Optional[str] = None  # None if skip vote
    vote_type: VoteType = VoteType.SKIP
    timestamp: float = 0.0


class MeetingState(BaseModel):
    """Tracks state of an active meeting."""
    started_at: float
    started_by: str  # player_id who called meeting
    started_by_name: str = ""  # caller name for display
    meeting_type: str = "meeting"  # "meeting" or "body_report"
    phase: str = "gathering"  # "gathering", "voting", or "results"
    votes: dict[str, Vote] = Field(default_factory=dict)  # voter_id -> Vote
    voting_ended: bool = False
    result: Optional[dict] = None  # Stores vote counts and outcome
    # Timestamps for server-side validation
    discussion_end_time: Optional[float] = None  # When discussion period ends
    voting_end_time: Optional[float] = None      # When voting timer expires


class GameModel(BaseModel):
    id: str = Field(default_factory=generate_id)
    code: str = Field(default_factory=generate_game_code)
    state: GameState = GameState.LOBBY
    settings: GameSettings = Field(default_factory=GameSettings)
    players: dict[str, PlayerModel] = Field(default_factory=dict)
    available_tasks: list[str] = Field(default_factory=lambda: DEFAULT_TASKS.copy())
    crewmate_task_total: int = 0
    winner: Optional[str] = None
    # Sabotage state
    active_sabotage: Optional[ActiveSabotage] = None
    sabotage_cooldown_end: Optional[float] = None  # timestamp when cooldown ends
    # Meeting/Voting state
    active_meeting: Optional[MeetingState] = None

    def get_task_completion_percentage(self) -> float:
        """Calculate task completion percentage (all crew-aligned roles)."""
        if self.crewmate_task_total == 0:
            return 0.0
        completed = sum(
            1 for p in self.players.values()
            if p.role and ROLE_CATEGORIES.get(p.role) == RoleCategory.CREW
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
    enable_sheriff: Optional[bool] = None
    kill_cooldown: Optional[int] = None  # Legacy
    impostor_kill_cooldown: Optional[int] = None
    sheriff_shoot_cooldown: Optional[int] = None
    lone_wolf_kill_cooldown: Optional[int] = None
    enable_impostor_timer: Optional[bool] = None
    enable_sheriff_timer: Optional[bool] = None
    enable_lone_wolf_timer: Optional[bool] = None
    vibrate_game_start: Optional[bool] = None
    vibrate_meeting: Optional[bool] = None
    vibrate_cooldown: Optional[bool] = None
    # Sabotage settings
    enable_sabotage: Optional[bool] = None
    sabotage_cooldown: Optional[int] = None
    sabotage_1_enabled: Optional[bool] = None
    sabotage_1_name: Optional[str] = None
    sabotage_1_timer: Optional[int] = None
    sabotage_2_enabled: Optional[bool] = None
    sabotage_2_name: Optional[str] = None
    sabotage_2_timer: Optional[int] = None
    sabotage_3_enabled: Optional[bool] = None
    sabotage_3_name: Optional[str] = None
    sabotage_3_timer: Optional[int] = None
    sabotage_4_enabled: Optional[bool] = None
    sabotage_4_name: Optional[str] = None
    sabotage_4_timer: Optional[int] = None
    # Meeting Timer & Voting settings
    meeting_timer_duration: Optional[int] = None
    meeting_warning_time: Optional[int] = None
    enable_voting: Optional[bool] = None
    anonymous_voting: Optional[bool] = None
    discussion_time: Optional[int] = None
    # Role configs
    role_configs: Optional[dict[str, dict]] = None  # {"engineer": {"enabled": true, "probability": 100}}


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


# Role descriptions for UI
ROLE_DESCRIPTIONS = {
    # Base roles
    "crewmate": {
        "name": "Crewmate",
        "category": "crew",
        "short": "Complete tasks and find impostors",
        "description": "Standard crew member. Complete tasks and vote out impostors to win.",
        "color": "#4ade80"
    },
    "impostor": {
        "name": "Impostor",
        "category": "impostor",
        "short": "Kill crewmates and avoid detection",
        "description": "Eliminate crewmates without getting caught. Sabotage to create chaos.",
        "color": "#ef4444"
    },
    # Existing special roles
    "jester": {
        "name": "Jester",
        "category": "neutral",
        "short": "Get voted out to win",
        "description": "Win by getting voted out during a meeting. Act suspicious!",
        "color": "#a855f7"
    },
    "lone_wolf": {
        "name": "Lone Wolf",
        "category": "neutral",
        "short": "Be the last one standing",
        "description": "Kill everyone - crew AND impostors. You win alone.",
        "color": "#f97316"
    },
    "minion": {
        "name": "Minion",
        "category": "crew",  # Appears as crew but wins with impostors
        "short": "Help impostors win (you don't know who they are)",
        "description": "You win with impostors but don't know who they are. Act like crew.",
        "color": "#eab308"
    },
    "sheriff": {
        "name": "Sheriff",
        "category": "crew",
        "short": "Shoot impostors (but die if you miss)",
        "description": "Can shoot players. Hit impostor = they die. Hit crew = YOU die.",
        "color": "#3b82f6"
    },
    # New Crewmate variants
    "engineer": {
        "name": "Engineer",
        "category": "crew",
        "short": "Fix one sabotage remotely",
        "description": "Once per game, fix any active sabotage from anywhere without going to the location.",
        "color": "#22c55e"
    },
    "captain": {
        "name": "Captain",
        "category": "crew",
        "short": "Call an extra emergency meeting",
        "description": "Has one additional emergency meeting button use beyond the normal limit.",
        "color": "#0ea5e9"
    },
    "mayor": {
        "name": "Mayor",
        "category": "crew",
        "short": "Your vote counts twice",
        "description": "During voting, your vote is worth 2 votes instead of 1.",
        "color": "#8b5cf6"
    },
    "nice_guesser": {
        "name": "Nice Guesser",
        "category": "crew",
        "short": "Guess roles during voting",
        "description": "Once per meeting, guess a player's role. Correct = they die. Wrong = YOU die.",
        "color": "#14b8a6"
    },
    "spy": {
        "name": "Spy",
        "category": "crew",
        "short": "Appear as impostor to impostors",
        "description": "Impostors see you as one of them, but you're actually crew. Use this to infiltrate.",
        "color": "#6366f1"
    },
    "swapper": {
        "name": "Swapper",
        "category": "crew",
        "short": "Swap votes between two players",
        "description": "During voting, select two players to swap all votes between them. Can't call meetings or fix lights.",
        "color": "#ec4899"
    },
    # New Impostor variants
    "evil_guesser": {
        "name": "Evil Guesser",
        "category": "impostor",
        "short": "Guess roles during voting",
        "description": "Once per meeting, guess a player's role. Correct = they die. Wrong = YOU die.",
        "color": "#dc2626"
    },
    "bounty_hunter": {
        "name": "Bounty Hunter",
        "category": "impostor",
        "short": "Faster kills on your target",
        "description": "You have a bounty target. Kill them faster, but others take longer. Target changes when killed.",
        "color": "#b91c1c"
    },
    "cleaner": {
        "name": "Cleaner",
        "category": "impostor",
        "short": "Clean up bodies",
        "description": "Can 'clean' bodies by moving them elsewhere. Tell the dead player to act alive until the next meeting.",
        "color": "#991b1b"
    },
    # New Neutral roles
    "vulture": {
        "name": "Vulture",
        "category": "neutral",
        "short": "Eat corpses to win",
        "description": "Find and 'eat' dead bodies. Eat enough corpses before game ends to win. Tell dead player they're eaten.",
        "color": "#84cc16"
    },
    "noise_maker": {
        "name": "Noise Maker",
        "category": "neutral",
        "short": "Choose who finds your body",
        "description": "When you die, select another player. They get a fake 'body found' notification from your location.",
        "color": "#f59e0b"
    },
}
