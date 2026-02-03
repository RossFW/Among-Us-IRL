"""Game logic: role assignment, win conditions, task distribution.

Ported from the original Discord bot at AmongUs_DC_Bot_9_16/main.py
"""

import random
from typing import Optional
from ..models import (
    GameModel, PlayerModel, TaskModel, Role, GameState,
    PlayerStatus, TaskStatus, RoleCategory, ROLE_CATEGORIES, RoleConfig
)


def roll_probability(probability: int) -> bool:
    """Roll for probability (0-100%). Returns True if success."""
    return random.randint(1, 100) <= probability


def assign_roles(game: GameModel) -> bool:
    """
    Assign roles to all players in the game.
    Returns True if successful, False if not enough players.

    Supports probability-based role selection for new roles.
    """
    players = list(game.players.values())
    num_players = len(players)
    settings = game.settings

    # Calculate total guaranteed special roles
    total_special = settings.num_impostors
    if settings.enable_jester:
        total_special += 1
    if settings.enable_lone_wolf:
        total_special += 1
    if settings.enable_minion:
        total_special += 1
    if settings.enable_sheriff:
        total_special += 1

    # Validate player count
    if num_players < total_special + 1:
        return False

    # Shuffle players for random assignment
    random.shuffle(players)

    role_index = 0
    assigned_roles = {}  # Track counts by role key

    # === PHASE 1: Assign Impostors (may be variants) ===
    impostor_variants = []
    for key in ["evil_guesser", "bounty_hunter", "cleaner", "venter"]:
        config = settings.role_configs.get(key, RoleConfig())
        if config.enabled and roll_probability(config.probability):
            impostor_variants.extend([key] * config.max_count)

    # Shuffle and limit to num_impostors
    random.shuffle(impostor_variants)
    impostor_variants = impostor_variants[:settings.num_impostors]

    # Fill remaining impostor slots with base Impostor
    while len(impostor_variants) < settings.num_impostors:
        impostor_variants.append("impostor")

    # Assign impostor roles
    role_map = {
        "impostor": Role.IMPOSTOR,
        "evil_guesser": Role.EVIL_GUESSER,
        "bounty_hunter": Role.BOUNTY_HUNTER,
        "cleaner": Role.CLEANER,
        "venter": Role.VENTER,
    }
    for variant in impostor_variants:
        players[role_index].role = role_map[variant]
        # Initialize bounty hunter target
        if variant == "bounty_hunter":
            # Will set target after all roles assigned
            pass
        role_index += 1

    # === PHASE 2: Assign legacy special roles ===
    if settings.enable_jester:
        players[role_index].role = Role.JESTER
        role_index += 1

    if settings.enable_lone_wolf:
        players[role_index].role = Role.LONE_WOLF
        role_index += 1

    if settings.enable_minion:
        players[role_index].role = Role.MINION
        role_index += 1

    if settings.enable_sheriff:
        players[role_index].role = Role.SHERIFF
        role_index += 1

    # === PHASE 3: Assign new neutral roles (probability-based) ===
    neutral_roles = []
    for key in ["vulture", "noise_maker"]:
        config = settings.role_configs.get(key, RoleConfig())
        if config.enabled and roll_probability(config.probability):
            for _ in range(min(config.max_count, num_players - role_index)):
                neutral_roles.append(key)

    neutral_map = {
        "vulture": Role.VULTURE,
        "noise_maker": Role.NOISE_MAKER,
    }
    for neutral_key in neutral_roles:
        if role_index < num_players:
            players[role_index].role = neutral_map[neutral_key]
            role_index += 1

    # === PHASE 4: Assign crewmate variants (probability-based) ===
    crew_variants = []
    for key in ["engineer", "captain", "mayor", "nice_guesser", "spy", "swapper"]:
        config = settings.role_configs.get(key, RoleConfig())
        if config.enabled and roll_probability(config.probability):
            for _ in range(config.max_count):
                crew_variants.append(key)

    random.shuffle(crew_variants)
    crew_map = {
        "engineer": Role.ENGINEER,
        "captain": Role.CAPTAIN,
        "mayor": Role.MAYOR,
        "nice_guesser": Role.NICE_GUESSER,
        "spy": Role.SPY,
        "swapper": Role.SWAPPER,
    }

    # Assign crew variants
    for crew_key in crew_variants:
        if role_index < num_players:
            players[role_index].role = crew_map[crew_key]
            role_index += 1

    # === PHASE 5: Fill remaining with Crewmate ===
    while role_index < num_players:
        players[role_index].role = Role.CREWMATE
        role_index += 1

    # === POST-ASSIGNMENT: Setup role-specific state ===
    # Initialize Bounty Hunter targets
    alive_non_impostors = [p for p in players if ROLE_CATEGORIES.get(p.role) != RoleCategory.IMPOSTOR]
    for player in players:
        if player.role == Role.BOUNTY_HUNTER and alive_non_impostors:
            player.bounty_target_id = random.choice(alive_non_impostors).id

    # Spy appears in impostor list (handled in get_role_info)

    return True


def distribute_tasks(game: GameModel):
    """
    Distribute tasks to all players.
    Crew-aligned roles get real tasks, others get fake tasks.

    Ported from main.py lines 220-240.
    """
    available = game.available_tasks.copy()
    tasks_per = game.settings.tasks_per_player
    task_doer_count = 0  # Crew-aligned roles

    for player in game.players.values():
        # Shuffle available tasks
        random.shuffle(available)

        # Select tasks for this player
        selected_tasks = available[:tasks_per]

        # Create task objects - Crew-aligned roles get real tasks
        is_crew = ROLE_CATEGORIES.get(player.role) == RoleCategory.CREW
        # Minion appears as crew but doesn't count for tasks
        is_minion = player.role == Role.MINION
        is_fake = not is_crew or is_minion

        player.tasks = [
            TaskModel(name=task_name, is_fake=is_fake)
            for task_name in selected_tasks
        ]

        # Only count actual crew members (not minion)
        if is_crew and not is_minion:
            task_doer_count += 1

    # Set total task count (crew-aligned roles minus minion)
    game.crewmate_task_total = task_doer_count * tasks_per


def start_game(game: GameModel) -> dict:
    """
    Start the game: assign roles and distribute tasks.
    Returns dict with success status and any adjustments made.
    """
    if game.state != GameState.LOBBY:
        return {"success": False, "error": "Game not in lobby"}

    num_players = len(game.players)
    if num_players < 4:
        return {"success": False, "error": "Need at least 4 players"}

    # Calculate total special roles needed
    total_special = game.settings.num_impostors
    if game.settings.enable_jester:
        total_special += 1
    if game.settings.enable_lone_wolf:
        total_special += 1
    if game.settings.enable_minion:
        total_special += 1
    if game.settings.enable_sheriff:
        total_special += 1

    adjustments = []

    # Auto-adjust impostors if too many for player count
    # Need at least 1 crewmate, so: impostors + other_special < num_players
    other_special = total_special - game.settings.num_impostors
    max_impostors = num_players - other_special - 1  # Leave room for 1 crewmate

    if max_impostors < 1:
        return {"success": False, "error": f"Not enough players for special roles. Need at least {other_special + 2} players."}

    if game.settings.num_impostors > max_impostors:
        old_count = game.settings.num_impostors
        game.settings.num_impostors = max_impostors
        adjustments.append(f"Impostors reduced from {old_count} to {max_impostors}")

    # Assign roles
    if not assign_roles(game):
        return {"success": False, "error": "Failed to assign roles"}

    # Distribute tasks
    distribute_tasks(game)

    # Update game state
    game.state = GameState.PLAYING

    return {"success": True, "adjustments": adjustments}


def check_win_conditions(game: GameModel) -> Optional[str]:
    """
    Check if any win condition is met.
    Returns the winner role name or None if game continues.

    Updated to use role categories for new roles.
    """
    if game.state not in [GameState.PLAYING, GameState.MEETING]:
        return None

    alive = game.get_alive_players()

    # Count alive by category
    num_impostor_team = sum(
        1 for p in alive
        if ROLE_CATEGORIES.get(p.role) == RoleCategory.IMPOSTOR
    )
    num_crew_team = sum(
        1 for p in alive
        if ROLE_CATEGORIES.get(p.role) == RoleCategory.CREW
    )
    num_neutral = sum(
        1 for p in alive
        if ROLE_CATEGORIES.get(p.role) == RoleCategory.NEUTRAL
    )

    # Check specific neutral roles
    lone_wolf_alive = any(p.role == Role.LONE_WOLF for p in alive)

    # Vulture win check - if any vulture has eaten enough bodies
    vulture_win_threshold = 3  # Number of bodies needed to win
    for player in game.players.values():
        if player.role == Role.VULTURE and player.vulture_bodies_eaten >= vulture_win_threshold:
            return "Vulture"

    # Task completion win (crew-aligned roles)
    if game.get_task_completion_percentage() >= 100:
        return "Crewmate"

    # Last one standing wins
    if len(alive) == 1:
        survivor = alive[0]
        category = ROLE_CATEGORIES.get(survivor.role)
        if survivor.role == Role.LONE_WOLF:
            return "Lone Wolf"
        if category == RoleCategory.IMPOSTOR:
            return "Impostor"
        if category == RoleCategory.CREW:
            return "Crewmate"

    # Lone Wolf vs Impostor: if only these two are left, game continues until one dies
    if len(alive) == 2 and lone_wolf_alive and num_impostor_team == 1:
        return None

    # All impostors dead = Crewmate win (unless Lone Wolf or other killers alive)
    if num_impostor_team == 0 and not lone_wolf_alive:
        return "Crewmate"

    # Impostor win: outnumber or equal crewmates, no lone wolf, at least 1 impostor
    # Note: Minion counts with impostors now via ROLE_CATEGORIES
    if not lone_wolf_alive and num_impostor_team >= num_crew_team and num_impostor_team > 0:
        return "Impostor"

    # Lone Wolf win: only crew left and it's just LW vs 1 crewmate
    if lone_wolf_alive and len(alive) == 2 and num_impostor_team == 0:
        return "Lone Wolf"

    # Game continues
    return None


def complete_task(game: GameModel, player_id: str, task_id: str) -> bool:
    """
    Mark a task as completed for a player.
    Returns True if successful.
    """
    player = game.players.get(player_id)
    # Crew-aligned roles (except Minion) can complete real tasks
    if not player:
        return False
    is_crew = ROLE_CATEGORIES.get(player.role) == RoleCategory.CREW
    is_minion = player.role == Role.MINION
    if not is_crew or is_minion:
        return False

    for task in player.tasks:
        if task.id == task_id and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.COMPLETED
            return True

    return False


def uncomplete_task(game: GameModel, player_id: str, task_id: str) -> bool:
    """
    Mark a task as pending for a player (undo completion).
    Returns True if successful.
    """
    player = game.players.get(player_id)
    # Crew-aligned roles (except Minion) can uncomplete real tasks
    if not player:
        return False
    is_crew = ROLE_CATEGORIES.get(player.role) == RoleCategory.CREW
    is_minion = player.role == Role.MINION
    if not is_crew or is_minion:
        return False

    for task in player.tasks:
        if task.id == task_id and task.status == TaskStatus.COMPLETED:
            task.status = TaskStatus.PENDING
            return True

    return False


def sheriff_shoot(game: GameModel, sheriff_id: str, target_id: str) -> dict:
    """
    Sheriff attempts to shoot a target.
    If target is impostor-aligned → target dies.
    If target is crew/neutral → sheriff dies.
    Returns dict with result info.
    """
    sheriff = game.players.get(sheriff_id)
    target = game.players.get(target_id)

    if not sheriff or sheriff.role != Role.SHERIFF:
        return {"success": False, "error": "Not a sheriff"}

    if sheriff.status != PlayerStatus.ALIVE:
        return {"success": False, "error": "Sheriff is dead"}

    if not target:
        return {"success": False, "error": "Target not found"}

    if target.status != PlayerStatus.ALIVE:
        return {"success": False, "error": "Target is already dead"}

    if target.id == sheriff.id:
        return {"success": False, "error": "Cannot shoot yourself"}

    # Determine outcome - hitting impostor-aligned roles is a success
    target_category = ROLE_CATEGORIES.get(target.role)
    if target_category == RoleCategory.IMPOSTOR:
        # Sheriff hit an impostor - target dies
        target.status = PlayerStatus.DEAD
        return {
            "success": True,
            "outcome": "hit",
            "dead_player_id": target.id,
            "dead_player_name": target.name,
            "message": f"{target.name} was an Impostor!"
        }
    else:
        # Sheriff missed (crew or neutral) - sheriff dies
        sheriff.status = PlayerStatus.DEAD
        return {
            "success": True,
            "outcome": "miss",
            "dead_player_id": sheriff.id,
            "dead_player_name": sheriff.name,
            "message": f"{target.name} was innocent. Sheriff is dead."
        }


def mark_player_dead(game: GameModel, player_id: str) -> bool:
    """
    Mark a player as dead.
    Returns True if successful.
    """
    player = game.players.get(player_id)
    if not player or player.status != PlayerStatus.ALIVE:
        return False

    player.status = PlayerStatus.DEAD
    return True


def get_role_info(player: PlayerModel, game: GameModel) -> dict:
    """Get role-specific information for a player."""
    info = {
        "role": player.role.value,
        "tasks": [
            {"id": t.id, "name": t.name, "status": t.status.value, "is_fake": t.is_fake}
            for t in player.tasks
        ]
    }

    # Impostor-aligned roles can see who the "impostors" are
    # This includes Spy (who appears as impostor to impostors)
    player_category = ROLE_CATEGORIES.get(player.role)
    if player_category == RoleCategory.IMPOSTOR or player.role == Role.MINION:
        # Show all impostor-aligned AND Spy
        info["fellow_impostors"] = [
            {"id": p.id, "name": p.name}
            for p in game.players.values()
            if p.id != player.id and (
                ROLE_CATEGORIES.get(p.role) == RoleCategory.IMPOSTOR or
                p.role == Role.SPY  # Spy appears as impostor to impostors
            )
        ]

    # Role-specific info
    if player.role == Role.BOUNTY_HUNTER and player.bounty_target_id:
        target = game.players.get(player.bounty_target_id)
        if target:
            info["bounty_target"] = {"id": target.id, "name": target.name}

    if player.role == Role.VULTURE:
        info["bodies_eaten"] = player.vulture_bodies_eaten
        info["bodies_needed"] = 2  # Win threshold

    if player.role == Role.ENGINEER:
        info["remote_fix_available"] = not player.engineer_fix_used

    if player.role == Role.CAPTAIN:
        info["extra_meeting_available"] = not player.captain_meeting_used

    if player.role in [Role.NICE_GUESSER, Role.EVIL_GUESSER]:
        info["guess_available_this_meeting"] = not player.guesser_used_this_meeting

    if player.role == Role.SWAPPER:
        info["swapper_targets"] = player.swapper_targets

    return info


def get_all_roles(game: GameModel) -> list[dict]:
    """Get all player roles (for game end reveal)."""
    return [
        {"id": p.id, "name": p.name, "role": p.role.value if p.role else None}
        for p in game.players.values()
    ]
