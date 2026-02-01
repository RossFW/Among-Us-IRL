"""Game logic: role assignment, win conditions, task distribution.

Ported from the original Discord bot at AmongUs_DC_Bot_9_16/main.py
"""

import random
from typing import Optional
from ..models import (
    GameModel, PlayerModel, TaskModel, Role, GameState,
    PlayerStatus, TaskStatus
)


def assign_roles(game: GameModel) -> bool:
    """
    Assign roles to all players in the game.
    Returns True if successful, False if not enough players.

    Ported from main.py lines 189-209.
    """
    players = list(game.players.values())
    num_players = len(players)

    settings = game.settings

    # Calculate total special roles needed
    total_special = settings.num_impostors
    if settings.enable_jester:
        total_special += 1
    if settings.enable_lone_wolf:
        total_special += 1
    if settings.enable_minion:
        total_special += 1

    # Validate player count
    if num_players < total_special + 1:
        return False

    # Shuffle players for random assignment
    random.shuffle(players)

    role_index = 0

    # Assign Impostors
    for i in range(settings.num_impostors):
        players[role_index].role = Role.IMPOSTOR
        role_index += 1

    # Assign Jester
    if settings.enable_jester:
        players[role_index].role = Role.JESTER
        role_index += 1

    # Assign Lone Wolf
    if settings.enable_lone_wolf:
        players[role_index].role = Role.LONE_WOLF
        role_index += 1

    # Assign Minion
    if settings.enable_minion:
        players[role_index].role = Role.MINION
        role_index += 1

    # Remaining players are Crewmates
    for i in range(role_index, num_players):
        players[role_index].role = Role.CREWMATE
        role_index += 1

    return True


def distribute_tasks(game: GameModel):
    """
    Distribute tasks to all players.
    Crewmates get real tasks, others get fake tasks.

    Ported from main.py lines 220-240.
    """
    available = game.available_tasks.copy()
    tasks_per = game.settings.tasks_per_player
    crewmate_count = 0

    for player in game.players.values():
        # Shuffle available tasks
        random.shuffle(available)

        # Select tasks for this player
        selected_tasks = available[:tasks_per]

        # Create task objects
        is_fake = player.role != Role.CREWMATE
        player.tasks = [
            TaskModel(name=task_name, is_fake=is_fake)
            for task_name in selected_tasks
        ]

        if player.role == Role.CREWMATE:
            crewmate_count += 1

    # Set total task count
    game.crewmate_task_total = crewmate_count * tasks_per


def start_game(game: GameModel) -> dict:
    """
    Start the game: assign roles and distribute tasks.
    Returns dict with success status and any adjustments made.
    """
    if game.state != GameState.LOBBY:
        return {"success": False, "error": "Game not in lobby"}

    num_players = len(game.players)
    if num_players < 2:
        return {"success": False, "error": "Need at least 2 players"}

    # Calculate total special roles needed
    total_special = game.settings.num_impostors
    if game.settings.enable_jester:
        total_special += 1
    if game.settings.enable_lone_wolf:
        total_special += 1
    if game.settings.enable_minion:
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

    Ported from main.py lines 375-400.
    """
    if game.state not in [GameState.PLAYING, GameState.MEETING]:
        return None

    alive = game.get_alive_players()

    # Count alive players by role
    num_impostors = sum(1 for p in alive if p.role == Role.IMPOSTOR)
    num_crewmates = sum(1 for p in alive if p.role == Role.CREWMATE)
    num_jesters = sum(1 for p in alive if p.role == Role.JESTER)
    num_minions = sum(1 for p in alive if p.role == Role.MINION)
    lone_wolf_alive = any(p.role == Role.LONE_WOLF for p in alive)

    impostor_team = num_impostors + num_minions
    crew_team = num_crewmates + num_jesters

    # Task completion win (Crewmates)
    if game.get_task_completion_percentage() >= 100:
        return "Crewmate"

    # Impostor win: outnumber crewmates, no lone wolf, at least 1 impostor
    if not lone_wolf_alive and impostor_team >= crew_team and num_impostors > 0:
        return "Impostor"

    # Lone Wolf win: last 2 alive, no impostors
    if lone_wolf_alive and len(alive) == 2 and num_impostors == 0:
        return "Lone Wolf"

    # All impostors dead but game continues (crewmates need to finish tasks)
    # Or game continues normally
    return None


def complete_task(game: GameModel, player_id: str, task_id: str) -> bool:
    """
    Mark a task as completed for a player.
    Returns True if successful.
    """
    player = game.players.get(player_id)
    if not player or player.role != Role.CREWMATE:
        return False

    for task in player.tasks:
        if task.id == task_id and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.COMPLETED
            return True

    return False


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

    # Impostors and Minions can see who the impostors are
    if player.role in [Role.IMPOSTOR, Role.MINION]:
        info["fellow_impostors"] = [
            {"id": p.id, "name": p.name}
            for p in game.players.values()
            if p.role == Role.IMPOSTOR and p.id != player.id
        ]

    return info


def get_all_roles(game: GameModel) -> list[dict]:
    """Get all player roles (for game end reveal)."""
    return [
        {"id": p.id, "name": p.name, "role": p.role.value if p.role else None}
        for p in game.players.values()
    ]
