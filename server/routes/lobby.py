"""Lobby routes: create game, join game, update settings."""

from fastapi import APIRouter, HTTPException
from ..database import game_store
from ..models import (
    CreateGameRequest, JoinGameRequest, UpdateSettingsRequest,
    AddTaskRequest, GameState, RoleConfig
)
from ..services.ws_manager import ws_manager

router = APIRouter(prefix="/api", tags=["lobby"])


@router.post("/games")
async def create_game(request: CreateGameRequest):
    """Create a new game and return the game code and session token."""
    if not request.player_name.strip():
        raise HTTPException(status_code=400, detail="Player name is required")

    game, host = game_store.create_game(request.player_name.strip())

    return {
        "code": game.code,
        "player_id": host.id,
        "session_token": host.session_token,
        "is_host": True
    }


@router.post("/games/{code}/join")
async def join_game(code: str, request: JoinGameRequest):
    """Join an existing game."""
    if not request.player_name.strip():
        raise HTTPException(status_code=400, detail="Player name is required")

    result = game_store.join_game(code.upper(), request.player_name.strip())
    if not result:
        raise HTTPException(status_code=404, detail="Game not found")

    game, player = result

    if game.state != GameState.LOBBY:
        raise HTTPException(status_code=400, detail="Game already started")

    # Notify other players
    await ws_manager.broadcast_to_game(game.code, {
        "type": "player_joined",
        "payload": {
            "player_id": player.id,
            "name": player.name
        }
    })

    return {
        "code": game.code,
        "player_id": player.id,
        "session_token": player.session_token,
        "is_host": False
    }


@router.get("/games/{code}")
async def get_game(code: str, session_token: str = None):
    """Get game state."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Find the requesting player if session provided
    current_player = None
    if session_token:
        current_player = game.get_player_by_session(session_token)

    # Build player list (hide roles unless game ended)
    players = []
    for p in game.players.values():
        player_info = {
            "id": p.id,
            "name": p.name,
            "is_host": p.is_host,
            "connected": p.connected,
            "status": p.status.value
        }
        # Only show roles at game end
        if game.state == GameState.ENDED:
            player_info["role"] = p.role.value if p.role else None

        players.append(player_info)

    return {
        "code": game.code,
        "state": game.state.value,
        "settings": game.settings.model_dump(),
        "players": players,
        "available_tasks": game.available_tasks,
        "task_percentage": game.get_task_completion_percentage(),
        "winner": game.winner
    }


@router.patch("/games/{code}/settings")
async def update_settings(code: str, request: UpdateSettingsRequest, session_token: str = None):
    """Update game settings (host only)."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.state != GameState.LOBBY:
        raise HTTPException(status_code=400, detail="Cannot change settings after game started")

    # Verify host
    if session_token:
        player = game.get_player_by_session(session_token)
        if not player or not player.is_host:
            raise HTTPException(status_code=403, detail="Only host can change settings")

    # Update settings
    if request.tasks_per_player is not None:
        game.settings.tasks_per_player = max(1, min(10, request.tasks_per_player))
    if request.num_impostors is not None:
        game.settings.num_impostors = max(1, min(3, request.num_impostors))
    if request.enable_jester is not None:
        game.settings.enable_jester = request.enable_jester
    if request.enable_lone_wolf is not None:
        game.settings.enable_lone_wolf = request.enable_lone_wolf
    if request.enable_minion is not None:
        game.settings.enable_minion = request.enable_minion
    if request.enable_sheriff is not None:
        game.settings.enable_sheriff = request.enable_sheriff
    if request.kill_cooldown is not None:
        game.settings.kill_cooldown = max(10, min(120, request.kill_cooldown))
    # Per-character cooldowns
    if request.impostor_kill_cooldown is not None:
        game.settings.impostor_kill_cooldown = max(10, min(120, request.impostor_kill_cooldown))
    if request.sheriff_shoot_cooldown is not None:
        game.settings.sheriff_shoot_cooldown = max(10, min(120, request.sheriff_shoot_cooldown))
    if request.lone_wolf_kill_cooldown is not None:
        game.settings.lone_wolf_kill_cooldown = max(10, min(120, request.lone_wolf_kill_cooldown))
    if request.enable_impostor_timer is not None:
        game.settings.enable_impostor_timer = request.enable_impostor_timer
    if request.enable_sheriff_timer is not None:
        game.settings.enable_sheriff_timer = request.enable_sheriff_timer
    if request.enable_lone_wolf_timer is not None:
        game.settings.enable_lone_wolf_timer = request.enable_lone_wolf_timer
    if request.vibrate_game_start is not None:
        game.settings.vibrate_game_start = request.vibrate_game_start
    if request.vibrate_meeting is not None:
        game.settings.vibrate_meeting = request.vibrate_meeting
    if request.vibrate_cooldown is not None:
        game.settings.vibrate_cooldown = request.vibrate_cooldown
    # Sabotage settings
    if request.enable_sabotage is not None:
        game.settings.enable_sabotage = request.enable_sabotage
    if request.sabotage_cooldown is not None:
        game.settings.sabotage_cooldown = max(10, min(120, request.sabotage_cooldown))
    if request.sabotage_1_enabled is not None:
        game.settings.sabotage_1_enabled = request.sabotage_1_enabled
    if request.sabotage_1_name is not None:
        game.settings.sabotage_1_name = request.sabotage_1_name[:20]
    if request.sabotage_1_timer is not None:
        game.settings.sabotage_1_timer = max(0, min(120, request.sabotage_1_timer))
    if request.sabotage_2_enabled is not None:
        game.settings.sabotage_2_enabled = request.sabotage_2_enabled
    if request.sabotage_2_name is not None:
        game.settings.sabotage_2_name = request.sabotage_2_name[:20]
    if request.sabotage_2_timer is not None:
        game.settings.sabotage_2_timer = max(0, min(120, request.sabotage_2_timer))
    if request.sabotage_3_enabled is not None:
        game.settings.sabotage_3_enabled = request.sabotage_3_enabled
    if request.sabotage_3_name is not None:
        game.settings.sabotage_3_name = request.sabotage_3_name[:20]
    if request.sabotage_3_timer is not None:
        game.settings.sabotage_3_timer = max(0, min(120, request.sabotage_3_timer))
    if request.sabotage_4_enabled is not None:
        game.settings.sabotage_4_enabled = request.sabotage_4_enabled
    if request.sabotage_4_name is not None:
        game.settings.sabotage_4_name = request.sabotage_4_name[:20]
    if request.sabotage_4_timer is not None:
        game.settings.sabotage_4_timer = max(0, min(120, request.sabotage_4_timer))
    # Meeting Timer & Voting settings
    if request.meeting_timer_duration is not None:
        game.settings.meeting_timer_duration = max(30, min(300, request.meeting_timer_duration))
    if request.meeting_warning_time is not None:
        # Warning time must be less than or equal to timer duration
        max_warning = game.settings.meeting_timer_duration
        game.settings.meeting_warning_time = max(0, min(max_warning, request.meeting_warning_time))
    if request.enable_voting is not None:
        game.settings.enable_voting = request.enable_voting
    if request.anonymous_voting is not None:
        game.settings.anonymous_voting = request.anonymous_voting
    if request.discussion_time is not None:
        game.settings.discussion_time = max(0, request.discussion_time)
    # Vulture settings
    if request.vulture_eat_count is not None:
        game.settings.vulture_eat_count = max(1, min(10, request.vulture_eat_count))
    # Post-vote results timer
    if request.vote_results_duration is not None:
        game.settings.vote_results_duration = max(5, min(30, request.vote_results_duration))

    # Role configs (probability-based roles)
    if request.role_configs is not None:
        for role_key, config_data in request.role_configs.items():
            if role_key in game.settings.role_configs:
                current_config = game.settings.role_configs[role_key]
                if "enabled" in config_data:
                    current_config.enabled = config_data["enabled"]
                if "probability" in config_data:
                    current_config.probability = max(0, min(100, config_data["probability"]))
                if "max_count" in config_data:
                    current_config.max_count = max(1, min(5, config_data["max_count"]))

    # Notify players
    await ws_manager.broadcast_to_game(game.code, {
        "type": "settings_changed",
        "payload": game.settings.model_dump()
    })

    return {"success": True, "settings": game.settings.model_dump()}


@router.post("/games/{code}/tasks")
async def add_task(code: str, request: AddTaskRequest, session_token: str = None):
    """Add a task to the available tasks."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    task_name = request.task_name.strip()
    if not task_name:
        raise HTTPException(status_code=400, detail="Task name is required")

    if task_name not in game.available_tasks:
        game.available_tasks.append(task_name)

    # Notify players
    await ws_manager.broadcast_to_game(game.code, {
        "type": "tasks_updated",
        "payload": {"tasks": game.available_tasks}
    })

    return {"success": True, "tasks": game.available_tasks}


@router.delete("/games/{code}/tasks/{task_name}")
async def remove_task(code: str, task_name: str, session_token: str = None):
    """Remove a task from the available tasks."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if task_name in game.available_tasks:
        game.available_tasks.remove(task_name)

    # Notify players
    await ws_manager.broadcast_to_game(game.code, {
        "type": "tasks_updated",
        "payload": {"tasks": game.available_tasks}
    })

    return {"success": True, "tasks": game.available_tasks}


@router.post("/reconnect")
async def reconnect(session_token: str):
    """Reconnect to an existing game session."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result
    player.connected = True

    return {
        "success": True,
        "code": game.code,
        "player_id": player.id,
        "is_host": player.is_host,
        "game_state": game.state.value
    }


@router.post("/games/{code}/leave")
async def leave_game(code: str, session_token: str):
    """Leave a game. If host leaves, transfer host to next player."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    player = game.get_player_by_session(session_token)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found in game")

    # Can only leave during lobby
    if game.state != GameState.LOBBY:
        raise HTTPException(status_code=400, detail="Cannot leave after game started")

    player_id = player.id
    player_name = player.name
    was_host = player.is_host

    # Remove player from game
    del game.players[player_id]

    # If host left and there are other players, transfer host
    new_host_name = None
    if was_host and game.players:
        # Get first player (by join order via dict insertion order)
        new_host = next(iter(game.players.values()))
        new_host.is_host = True
        new_host_name = new_host.name

    # If no players left, delete the game
    if not game.players:
        game_store.delete_game(code.upper())
        return {"success": True, "game_deleted": True}

    # Notify remaining players
    await ws_manager.broadcast_to_game(game.code, {
        "type": "player_left",
        "payload": {
            "player_id": player_id,
            "name": player_name,
            "was_host": was_host,
            "new_host": new_host_name
        }
    })

    return {"success": True, "game_deleted": False}


@router.post("/test/join")
async def test_join_or_create():
    """Test mode: atomically join or create a game with code TEST.

    Single endpoint eliminates race conditions - no separate check step.
    """
    code = "TEST"
    game = game_store.get_game(code)

    if game and game.state == GameState.LOBBY:
        # Join existing game
        player_name = f"Player {len(game.players) + 1}"
        result = game_store.join_game(code, player_name)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to join game")
        game, player = result

        # Notify other players via WebSocket
        await ws_manager.broadcast_to_game(game.code, {
            "type": "player_joined",
            "payload": {
                "player_id": player.id,
                "name": player.name
            }
        })

        return {
            "code": game.code,
            "player_id": player.id,
            "player_name": player.name,
            "session_token": player.session_token,
            "is_host": False
        }
    else:
        # No game or game not in lobby - create fresh
        game, host = game_store.create_game_with_code("Player 1", code)

        return {
            "code": game.code,
            "player_id": host.id,
            "player_name": host.name,
            "session_token": host.session_token,
            "is_host": True
        }
