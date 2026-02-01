"""Lobby routes: create game, join game, update settings."""

from fastapi import APIRouter, HTTPException
from ..database import game_store
from ..models import (
    CreateGameRequest, JoinGameRequest, UpdateSettingsRequest,
    AddTaskRequest, GameState
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
