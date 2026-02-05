"""Sabotage routes."""

from fastapi import APIRouter, HTTPException
from ..database import game_store
from ..models import GameState, PlayerStatus, ActiveSabotage, Role
import time
from ..services.ws_manager import ws_manager
from ..services.game_logic import check_win_conditions, get_all_roles

router = APIRouter(prefix="/api", tags=["sabotage"])


@router.post("/games/{code}/sabotage/start")
async def start_sabotage_endpoint(code: str, sabotage_index: int, session_token: str):
    """Start a sabotage (impostor only, alive or dead)."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    # Must be impostor-aligned (except Minion) — alive or dead can trigger
    impostor_sabotage_roles = [Role.IMPOSTOR, Role.EVIL_GUESSER, Role.BOUNTY_HUNTER, Role.CLEANER, Role.VENTER]
    if player.role not in impostor_sabotage_roles:
        raise HTTPException(status_code=403, detail="Only impostors can sabotage")

    # Game must be in progress (not meeting, not ended)
    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Cannot sabotage now")

    # Check sabotage is enabled
    if not game.settings.enable_sabotage:
        raise HTTPException(status_code=400, detail="Sabotage is disabled")

    # Check no active sabotage
    if game.active_sabotage is not None:
        raise HTTPException(status_code=400, detail="Sabotage already active")

    # Check cooldown
    if game.sabotage_cooldown_end and time.time() < game.sabotage_cooldown_end:
        remaining = int(game.sabotage_cooldown_end - time.time())
        raise HTTPException(status_code=400, detail=f"Sabotage on cooldown ({remaining}s)")

    # Get sabotage settings
    if sabotage_index < 1 or sabotage_index > 4:
        raise HTTPException(status_code=400, detail="Invalid sabotage index")

    enabled = getattr(game.settings, f"sabotage_{sabotage_index}_enabled")
    if not enabled:
        raise HTTPException(status_code=400, detail="This sabotage is disabled")

    name = getattr(game.settings, f"sabotage_{sabotage_index}_name")
    sab_type = getattr(game.settings, f"sabotage_{sabotage_index}_type")
    timer = getattr(game.settings, f"sabotage_{sabotage_index}_timer")

    # Create active sabotage
    game.active_sabotage = ActiveSabotage(
        index=sabotage_index,
        type=sab_type,
        name=name,
        timer=timer,
        started_at=time.time(),
        started_by=player.id
    )

    # Broadcast sabotage started
    await ws_manager.broadcast_to_game(game.code, {
        "type": "sabotage_started",
        "payload": {
            "index": sabotage_index,
            "type": sab_type,
            "name": name,
            "timer": timer,
            "started_by": player.name
        }
    })

    return {"success": True, "sabotage": name}


@router.post("/games/{code}/sabotage/fix")
async def fix_sabotage_endpoint(code: str, session_token: str, action: str = "tap"):
    """Fix sabotage. action: 'tap' for lights/o2, 'hold_start'/'hold_end' for reactor."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    # Must be alive to fix
    if player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="Dead players cannot fix sabotage")

    # Must have active sabotage
    if game.active_sabotage is None:
        raise HTTPException(status_code=400, detail="No active sabotage")

    sab = game.active_sabotage
    resolved = False
    message = ""

    if sab.type == "lights":
        # Lights: 1 tap to fix
        resolved = True
        message = f"{player.name} fixed the lights!"

    elif sab.type == "reactor":
        # Reactor: 2 people must hold simultaneously
        if action == "hold_start":
            if player.id not in sab.reactor_holders:
                sab.reactor_holders.append(player.id)
            # Check if 2 people holding
            if len(sab.reactor_holders) >= 2:
                resolved = True
                message = "Reactor meltdown averted!"
            else:
                # Notify others someone is holding
                await ws_manager.broadcast_to_game(game.code, {
                    "type": "sabotage_update",
                    "payload": {
                        "type": "reactor",
                        "holders": len(sab.reactor_holders),
                        "holder_name": player.name
                    }
                })
                return {"success": True, "holding": True, "holders": len(sab.reactor_holders)}
        elif action == "hold_end":
            if player.id in sab.reactor_holders:
                sab.reactor_holders.remove(player.id)
            await ws_manager.broadcast_to_game(game.code, {
                "type": "sabotage_update",
                "payload": {
                    "type": "reactor",
                    "holders": len(sab.reactor_holders)
                }
            })
            return {"success": True, "holding": False, "holders": len(sab.reactor_holders)}

    elif sab.type == "o2":
        # O2: 2 switches total
        sab.o2_switches += 1
        if sab.o2_switches >= 2:
            resolved = True
            message = "O2 restored!"
        else:
            # Notify progress
            await ws_manager.broadcast_to_game(game.code, {
                "type": "sabotage_update",
                "payload": {
                    "type": "o2",
                    "switches": sab.o2_switches,
                    "fixer_name": player.name
                }
            })
            return {"success": True, "switches": sab.o2_switches}

    if resolved:
        game.active_sabotage = None
        # Set cooldown
        game.sabotage_cooldown_end = time.time() + game.settings.sabotage_cooldown

        await ws_manager.broadcast_to_game(game.code, {
            "type": "sabotage_resolved",
            "payload": {
                "type": sab.type,
                "name": sab.name,
                "resolved_by": player.name,
                "message": message
            }
        })

    return {"success": True, "resolved": resolved}


@router.post("/games/{code}/sabotage/check_timeout")
async def check_sabotage_timeout_endpoint(code: str, session_token: str):
    """Check if sabotage timer expired (called by clients periodically)."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    # If game already ended (e.g., neutral win), don't process sabotage timeout
    if game.state == GameState.ENDED:
        return {"success": True, "expired": False}

    if game.active_sabotage is None:
        return {"success": True, "expired": False}

    sab = game.active_sabotage

    # Check if timer expired
    if sab.timer > 0:
        elapsed = time.time() - sab.started_at
        if elapsed >= sab.timer:
            # Impostor wins!
            game.state = GameState.ENDED
            game.winner = "Impostor"
            game.active_sabotage = None

            await ws_manager.broadcast_to_game(game.code, {
                "type": "game_ended",
                "payload": {
                    "winner": "Impostor",
                    "reason": f"{sab.name} was not fixed in time!",
                    "roles": get_all_roles(game)
                }
            })

            return {"success": True, "expired": True, "winner": "Impostor"}

    return {"success": True, "expired": False}


@router.get("/games/{code}/sabotage/status")
async def get_sabotage_status_endpoint(code: str, session_token: str):
    """Get current sabotage status."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if game.active_sabotage is None:
        cooldown_remaining = 0
        if game.sabotage_cooldown_end:
            cooldown_remaining = max(0, int(game.sabotage_cooldown_end - time.time()))
        return {
            "active": False,
            "cooldown_remaining": cooldown_remaining
        }

    sab = game.active_sabotage
    elapsed = time.time() - sab.started_at
    remaining = max(0, sab.timer - elapsed) if sab.timer > 0 else 0

    return {
        "active": True,
        "type": sab.type,
        "name": sab.name,
        "timer": sab.timer,
        "remaining": int(remaining),
        "reactor_holders": len(sab.reactor_holders) if sab.type == "reactor" else 0,
        "o2_switches": sab.o2_switches if sab.type == "o2" else 0
    }
