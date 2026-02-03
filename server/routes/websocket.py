"""WebSocket route for real-time game updates."""

import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..database import game_store
from ..services.ws_manager import ws_manager
from ..services.game_logic import get_role_info

router = APIRouter()


@router.websocket("/ws/{game_code}/{session_token}")
async def websocket_endpoint(websocket: WebSocket, game_code: str, session_token: str):
    """WebSocket connection for real-time game updates."""

    # Validate session and get player
    result = game_store.get_player_by_session(session_token)
    if not result:
        await websocket.close(code=4001, reason="Invalid session")
        return

    game, player = result

    # Verify game code matches
    if game.code != game_code.upper():
        await websocket.close(code=4002, reason="Game code mismatch")
        return

    # Connect
    await ws_manager.connect(game_code.upper(), player.id, websocket)
    player.connected = True

    # Send current state on connect
    state_payload = {
        "type": "state_sync",
        "payload": {
            "game_state": game.state.value,
            "task_percentage": game.get_task_completion_percentage(),
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "is_host": p.is_host,
                    "connected": p.connected,
                    "status": p.status.value
                }
                for p in game.players.values()
            ]
        }
    }

    # Add role info if game started
    if player.role:
        state_payload["payload"]["role_info"] = get_role_info(player, game)

    # Add winner if game ended
    if game.winner:
        state_payload["payload"]["winner"] = game.winner

    # Add active sabotage if any
    if game.active_sabotage:
        sab = game.active_sabotage
        elapsed = time.time() - sab.started_at
        remaining = max(0, sab.timer - elapsed) if sab.timer > 0 else 0
        state_payload["payload"]["active_sabotage"] = {
            "index": sab.index,
            "type": sab.type,
            "name": sab.name,
            "timer": int(remaining),
            "reactor_holders": len(sab.reactor_holders),
            "o2_switches": sab.o2_switches
        }

    # Add active meeting state for reconnection
    if game.active_meeting:
        meeting = game.active_meeting
        now = time.time()
        state_payload["payload"]["active_meeting"] = {
            "phase": meeting.phase,
            "meeting_type": meeting.meeting_type,
            "caller_id": meeting.started_by,
            "caller_name": meeting.started_by_name,
            "has_voted": player.id in meeting.votes,
            "votes_cast": len(meeting.votes),
            "votes_needed": len(game.get_alive_players()),
            "discussion_ends_at": meeting.discussion_end_time,
            "voting_ends_at": meeting.voting_end_time,
            "discussion_remaining": max(0, meeting.discussion_end_time - now) if meeting.discussion_end_time else 0,
            "voting_remaining": max(0, meeting.voting_end_time - now) if meeting.voting_end_time else 0,
            "alive_players": [{"id": p.id, "name": p.name} for p in game.get_alive_players()],
            "dead_players": [{"id": p.id, "name": p.name} for p in game.get_dead_players()],
            "result": meeting.result
        }

    await websocket.send_json(state_payload)

    # Notify others that player connected
    await ws_manager.broadcast_to_game(game_code.upper(), {
        "type": "player_connected",
        "payload": {"player_id": player.id, "name": player.name}
    }, exclude_player=player.id)

    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_json()

            # Handle ping/pong for keepalive
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        player.connected = False
        ws_manager.disconnect(game_code.upper(), player.id)

        # Notify others
        await ws_manager.broadcast_to_game(game_code.upper(), {
            "type": "player_disconnected",
            "payload": {"player_id": player.id, "name": player.name}
        })
