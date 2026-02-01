"""Game routes: start, end, actions during gameplay."""

from fastapi import APIRouter, HTTPException
from ..database import game_store
from ..models import GameState, PlayerStatus
from ..services.ws_manager import ws_manager
from ..services.game_logic import (
    start_game, complete_task, mark_player_dead,
    check_win_conditions, get_role_info, get_all_roles
)

router = APIRouter(prefix="/api", tags=["game"])


@router.post("/games/{code}/start")
async def start_game_endpoint(code: str, session_token: str = None):
    """Start the game (host only)."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Verify host
    if session_token:
        player = game.get_player_by_session(session_token)
        if not player or not player.is_host:
            raise HTTPException(status_code=403, detail="Only host can start game")

    if game.state != GameState.LOBBY:
        raise HTTPException(status_code=400, detail="Game already started")

    # Start the game (this now auto-adjusts settings if needed)
    result = start_game(game)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to start game"))

    # Send role info to each player via WebSocket
    for player in game.players.values():
        role_info = get_role_info(player, game)
        await ws_manager.send_to_player(game.code, player.id, {
            "type": "game_started",
            "payload": {
                **role_info,
                "task_percentage": game.get_task_completion_percentage(),
                "adjustments": result.get("adjustments", [])
            }
        })

    return {"success": True, "state": game.state.value, "adjustments": result.get("adjustments", [])}


@router.post("/games/{code}/end")
async def end_game_endpoint(code: str, session_token: str = None):
    """End the game early (host only)."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Verify host
    if session_token:
        player = game.get_player_by_session(session_token)
        if not player or not player.is_host:
            raise HTTPException(status_code=403, detail="Only host can end game")

    game.state = GameState.ENDED
    game.winner = "Cancelled"

    # Notify all players
    await ws_manager.broadcast_to_game(game.code, {
        "type": "game_ended",
        "payload": {
            "winner": game.winner,
            "roles": get_all_roles(game)
        }
    })

    return {"success": True}


@router.post("/tasks/{task_id}/complete")
async def complete_task_endpoint(task_id: str, session_token: str):
    """Mark a task as completed."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in progress")

    if not complete_task(game, player.id, task_id):
        raise HTTPException(status_code=400, detail="Cannot complete task")

    task_percentage = game.get_task_completion_percentage()

    # Broadcast task progress update
    await ws_manager.broadcast_to_game(game.code, {
        "type": "task_completed",
        "payload": {
            "task_percentage": task_percentage
        }
    })

    # Check win conditions
    winner = check_win_conditions(game)
    if winner:
        game.state = GameState.ENDED
        game.winner = winner
        await ws_manager.broadcast_to_game(game.code, {
            "type": "game_ended",
            "payload": {
                "winner": winner,
                "roles": get_all_roles(game)
            }
        })

    return {"success": True, "task_percentage": task_percentage}


@router.post("/players/{player_id}/die")
async def mark_dead_endpoint(player_id: str, session_token: str):
    """Mark self as dead."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    # Can only mark yourself as dead
    if player.id != player_id:
        raise HTTPException(status_code=403, detail="Can only mark yourself as dead")

    if game.state not in [GameState.PLAYING, GameState.MEETING]:
        raise HTTPException(status_code=400, detail="Game not in progress")

    if not mark_player_dead(game, player_id):
        raise HTTPException(status_code=400, detail="Already dead")

    # Broadcast death
    await ws_manager.broadcast_to_game(game.code, {
        "type": "player_died",
        "payload": {
            "player_id": player.id,
            "name": player.name
        }
    })

    # Check win conditions
    winner = check_win_conditions(game)
    if winner:
        game.state = GameState.ENDED
        game.winner = winner
        await ws_manager.broadcast_to_game(game.code, {
            "type": "game_ended",
            "payload": {
                "winner": winner,
                "roles": get_all_roles(game)
            }
        })

    return {"success": True}


@router.post("/games/{code}/meeting/start")
async def start_meeting_endpoint(code: str, session_token: str):
    """Call a meeting."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in playing state")

    # Verify player is alive
    player = game.get_player_by_session(session_token)
    if not player or player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=403, detail="Only alive players can call meetings")

    game.state = GameState.MEETING

    # Broadcast meeting start
    await ws_manager.broadcast_to_game(game.code, {
        "type": "meeting_called",
        "payload": {
            "called_by": player.name,
            "task_percentage": game.get_task_completion_percentage(),
            "alive_players": [
                {"id": p.id, "name": p.name}
                for p in game.get_alive_players()
            ],
            "dead_players": [
                {"id": p.id, "name": p.name}
                for p in game.get_dead_players()
            ]
        }
    })

    return {"success": True}


@router.post("/games/{code}/meeting/end")
async def end_meeting_endpoint(code: str, session_token: str):
    """End the current meeting."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.state != GameState.MEETING:
        raise HTTPException(status_code=400, detail="No meeting in progress")

    game.state = GameState.PLAYING

    # Broadcast meeting end
    await ws_manager.broadcast_to_game(game.code, {
        "type": "meeting_ended",
        "payload": {}
    })

    # Check win conditions after meeting
    winner = check_win_conditions(game)
    if winner:
        game.state = GameState.ENDED
        game.winner = winner
        await ws_manager.broadcast_to_game(game.code, {
            "type": "game_ended",
            "payload": {
                "winner": winner,
                "roles": get_all_roles(game)
            }
        })

    return {"success": True}


@router.get("/players/me")
async def get_my_info(session_token: str):
    """Get current player info including role and tasks."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    response = {
        "id": player.id,
        "name": player.name,
        "is_host": player.is_host,
        "status": player.status.value,
        "game_code": game.code,
        "game_state": game.state.value
    }

    # Include role info if game has started
    if game.state != GameState.LOBBY and player.role:
        response.update(get_role_info(player, game))
        response["task_percentage"] = game.get_task_completion_percentage()

    # Include winner info if game ended
    if game.state == GameState.ENDED:
        response["winner"] = game.winner
        response["all_roles"] = get_all_roles(game)

    return response
