"""Game routes: start, end, core gameplay actions."""

from fastapi import APIRouter, HTTPException
from ..database import game_store
from ..models import GameState, PlayerStatus, Role, ROLE_DESCRIPTIONS
from ..services.ws_manager import ws_manager
from ..services.game_logic import (
    start_game, complete_task, uncomplete_task, mark_player_dead,
    check_win_conditions, get_role_info, get_all_roles, sheriff_shoot
)
from ..services.game_helpers import check_and_reassign_bounty_targets, check_executioner_fallback, check_lookout_notify

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
    game.active_sabotage = None

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
        game.active_sabotage = None
        await ws_manager.broadcast_to_game(game.code, {
            "type": "game_ended",
            "payload": {
                "winner": winner,
                "roles": get_all_roles(game)
            }
        })

    return {"success": True, "task_percentage": task_percentage}


@router.post("/tasks/{task_id}/uncomplete")
async def uncomplete_task_endpoint(task_id: str, session_token: str):
    """Mark a task as pending (undo completion)."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in progress")

    if not uncomplete_task(game, player.id, task_id):
        raise HTTPException(status_code=400, detail="Cannot uncomplete task")

    task_percentage = game.get_task_completion_percentage()

    # Broadcast task progress update
    await ws_manager.broadcast_to_game(game.code, {
        "type": "task_completed",
        "payload": {
            "task_percentage": task_percentage
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

    # Handle role-specific reactions to death
    await check_and_reassign_bounty_targets(game, player.id)
    await check_executioner_fallback(game, player.id)
    await check_lookout_notify(game, player.id)

    # Check win conditions
    winner = check_win_conditions(game)
    if winner:
        game.state = GameState.ENDED
        game.winner = winner
        game.active_sabotage = None
        await ws_manager.broadcast_to_game(game.code, {
            "type": "game_ended",
            "payload": {
                "winner": winner,
                "roles": get_all_roles(game)
            }
        })

    # Noise Maker: return flag so frontend shows target selection
    # Only during PLAYING (not during meetings - voted out doesn't trigger)
    is_noise_maker = player.role == Role.NOISE_MAKER and game.state == GameState.PLAYING

    return {"success": True, "noise_maker": is_noise_maker}


@router.post("/players/{player_id}/jester-win")
async def jester_win_endpoint(player_id: str, session_token: str):
    """Jester claims victory by being voted out."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    # Can only claim for yourself
    if player.id != player_id:
        raise HTTPException(status_code=403, detail="Can only claim your own victory")

    # Must be a Jester
    if player.role != Role.JESTER:
        raise HTTPException(status_code=403, detail="Only Jester can use this")

    if game.state not in [GameState.PLAYING, GameState.MEETING]:
        raise HTTPException(status_code=400, detail="Game not in progress")

    # Jester wins!
    game.state = GameState.ENDED
    game.winner = "Jester"
    game.active_sabotage = None

    await ws_manager.broadcast_to_game(game.code, {
        "type": "game_ended",
        "payload": {
            "winner": "Jester",
            "roles": get_all_roles(game)
        }
    })

    return {"success": True}


@router.post("/sheriff/shoot/{target_id}")
async def sheriff_shoot_endpoint(target_id: str, session_token: str):
    """Sheriff shoots a target player."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in progress")

    shoot_result = sheriff_shoot(game, player.id, target_id)
    if not shoot_result["success"]:
        raise HTTPException(status_code=400, detail=shoot_result.get("error", "Cannot shoot"))

    # Broadcast the death
    await ws_manager.broadcast_to_game(game.code, {
        "type": "player_died",
        "payload": {
            "player_id": shoot_result["dead_player_id"],
            "name": shoot_result["dead_player_name"],
            "cause": "sheriff_shot",
            "outcome": shoot_result["outcome"],
            "message": shoot_result["message"]
        }
    })

    # Handle role-specific reactions to death
    dead_id = shoot_result["dead_player_id"]
    await check_and_reassign_bounty_targets(game, dead_id)
    await check_executioner_fallback(game, dead_id)
    await check_lookout_notify(game, dead_id)

    # Check win conditions
    winner = check_win_conditions(game)
    if winner:
        game.state = GameState.ENDED
        game.winner = winner
        game.active_sabotage = None
        await ws_manager.broadcast_to_game(game.code, {
            "type": "game_ended",
            "payload": {
                "winner": winner,
                "roles": get_all_roles(game)
            }
        })

    return {"success": True, **shoot_result}


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


@router.get("/games/{code}/role-guide")
async def get_role_guide(code: str, session_token: str = None):
    """Get role descriptions for all enabled roles in this game."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    s = game.settings
    enabled_roles = ["crewmate", "impostor"]

    # All roles are now in role_configs
    for key, config in s.role_configs.items():
        if config.enabled and key not in enabled_roles:
            enabled_roles.append(key)

    # Build response grouped by category
    guide = {"crew": [], "impostor": [], "neutral": []}
    for role_key in enabled_roles:
        desc = ROLE_DESCRIPTIONS.get(role_key)
        if desc:
            category = desc["category"]
            if category in guide:
                guide[category].append(desc)

    return guide
