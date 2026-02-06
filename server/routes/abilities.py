"""Role ability routes."""

from fastapi import APIRouter, HTTPException
from ..database import game_store
from ..models import GameState, PlayerStatus, Role, MeetingState, Vote, VoteType, ROLE_CATEGORIES, RoleCategory
import time
from ..services.ws_manager import ws_manager
from ..services.game_logic import check_win_conditions, get_role_info, reassign_bounty_target, get_all_roles
from ..services.game_helpers import check_and_reassign_bounty_targets

router = APIRouter(prefix="/api", tags=["abilities"])


@router.post("/games/{code}/ability/engineer-fix")
async def engineer_fix_endpoint(code: str, session_token: str):
    """Engineer: Fix active sabotage remotely (one use per game)."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if player.role != Role.ENGINEER:
        raise HTTPException(status_code=403, detail="Not an Engineer")

    if player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="You are dead")

    if player.engineer_fix_used:
        raise HTTPException(status_code=400, detail="Already used remote fix this game")

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Cannot use ability now")

    if game.active_sabotage is None:
        raise HTTPException(status_code=400, detail="No active sabotage to fix")

    # Mark ability as used
    player.engineer_fix_used = True

    # Fix the sabotage
    sabotage_name = game.active_sabotage.name
    game.active_sabotage = None

    # Broadcast sabotage resolved
    await ws_manager.broadcast_to_game(game.code, {
        "type": "sabotage_resolved",
        "payload": {
            "resolver": player.name,
            "sabotage_name": sabotage_name,
            "method": "Engineer remote fix"
        }
    })

    return {"success": True, "message": f"Fixed {sabotage_name} remotely!"}


@router.post("/games/{code}/ability/captain-meeting")
async def captain_meeting_endpoint(code: str, session_token: str):
    """Captain: Call a remote meeting from anywhere (one use per game)."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if player.role != Role.CAPTAIN:
        raise HTTPException(status_code=403, detail="Not a Captain")

    if player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="You are dead")

    if player.captain_meeting_used:
        raise HTTPException(status_code=400, detail="Already used remote meeting this game")

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Cannot call meeting now")

    if game.active_meeting is not None:
        raise HTTPException(status_code=400, detail="Meeting already in progress")

    if game.active_sabotage is not None:
        raise HTTPException(status_code=400, detail="Cannot call meeting during sabotage")

    # Mark ability as used
    player.captain_meeting_used = True

    # Mark all currently dead bodies as ineligible for vulture eating
    for p in game.players.values():
        if p.status == PlayerStatus.DEAD and p.id not in game.vulture_ineligible_body_ids:
            game.vulture_ineligible_body_ids.append(p.id)

    # Create meeting state (same as normal meeting)
    game.active_meeting = MeetingState(
        started_at=time.time(),
        started_by=player.id,
        started_by_name=player.name,
        meeting_type="meeting",
        phase="gathering"
    )
    game.state = GameState.MEETING

    # Broadcast meeting with full payload (same as normal meeting)
    await ws_manager.broadcast_to_game(game.code, {
        "type": "meeting_called",
        "payload": {
            "called_by": player.name,
            "caller_id": player.id,
            "meeting_type": "meeting",
            "phase": "gathering",
            "task_percentage": game.get_task_completion_percentage(),
            "alive_players": [
                {"id": p.id, "name": p.name}
                for p in game.get_alive_players()
            ],
            "dead_players": [
                {"id": p.id, "name": p.name}
                for p in game.get_dead_players()
            ],
            "enable_voting": game.settings.enable_voting,
            "anonymous_voting": game.settings.anonymous_voting,
            "timer_duration": game.settings.meeting_timer_duration,
            "warning_time": game.settings.meeting_warning_time,
            "discussion_time": game.settings.discussion_time
        }
    })

    return {"success": True}


@router.post("/games/{code}/ability/guesser-guess")
async def guesser_guess_endpoint(code: str, session_token: str, target_id: str, guessed_role: str):
    """Guesser: Guess a player's role during meeting. Wrong = you die."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if player.role not in [Role.NICE_GUESSER, Role.EVIL_GUESSER]:
        raise HTTPException(status_code=403, detail="Not a Guesser")

    if player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="You are dead")

    if game.state != GameState.MEETING:
        raise HTTPException(status_code=400, detail="Can only guess during meetings")

    if player.guesser_used_this_meeting:
        raise HTTPException(status_code=400, detail="Already guessed wrong this meeting")

    target = game.players.get(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    if target.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="Target is already dead")

    # Check if guess is correct
    try:
        guessed = Role(guessed_role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")

    # Crew guesser (Bounty Hunter): "Impostor" guess matches ANY impostor-category role
    if player.role == Role.NICE_GUESSER and guessed == Role.IMPOSTOR:
        is_correct = ROLE_CATEGORIES.get(target.role) == RoleCategory.IMPOSTOR
    else:
        is_correct = target.role == guessed

    if is_correct:
        # Correct! Target dies. Guesser can keep guessing.
        target.status = PlayerStatus.DEAD
        dead_player = target
        guesser_survived = True
        message = f"{target.name} has been eliminated."
    else:
        # Wrong! Guesser dies. Mark as used so they can't guess again.
        player.guesser_used_this_meeting = True
        player.status = PlayerStatus.DEAD
        dead_player = player
        guesser_survived = False
        message = f"{player.name} has been eliminated."

    # Scrub dead player's vote if they already voted
    if game.active_meeting and dead_player.id in game.active_meeting.votes:
        del game.active_meeting.votes[dead_player.id]

    # Auto-reassign bounty targets if the dead player was someone's target
    await check_and_reassign_bounty_targets(game, dead_player.id)

    # Calculate updated vote counts
    alive_count = sum(1 for p in game.players.values() if p.status == PlayerStatus.ALIVE)
    votes_cast = len(game.active_meeting.votes) if game.active_meeting else 0

    # Broadcast result
    await ws_manager.broadcast_to_game(game.code, {
        "type": "guesser_result",
        "payload": {
            "guesser_name": player.name,
            "guesser_id": player.id,
            "target_name": target.name,
            "target_id": target.id,
            "guessed_role": guessed_role,
            "correct": guesser_survived,
            "dead_player_id": dead_player.id,
            "dead_player_name": dead_player.name,
            "message": message,
            "votes_cast": votes_cast,
            "votes_needed": alive_count
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

    return {"success": True, "correct": guesser_survived, "message": message}


@router.post("/games/{code}/ability/noise-maker-select")
async def noise_maker_select_endpoint(code: str, session_token: str, target_player_id: str):
    """Noise Maker: Select who 'finds' your body. Triggers a body report meeting on that player."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if player.role != Role.NOISE_MAKER:
        raise HTTPException(status_code=403, detail="Not a Noise Maker")

    if player.status != PlayerStatus.DEAD:
        raise HTTPException(status_code=400, detail="You must be dead to use this ability")

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Can only use during gameplay")

    if game.active_meeting:
        raise HTTPException(status_code=400, detail="Meeting already in progress")

    target = game.players.get(target_player_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    if target.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="Target must be alive")

    # Store the target selection
    player.noise_maker_target_id = target_player_id

    # Trigger a body report meeting with the target as the "caller"
    # Mark all currently dead bodies as ineligible for vulture eating
    for p in game.players.values():
        if p.status == PlayerStatus.DEAD and p.id not in game.vulture_ineligible_body_ids:
            game.vulture_ineligible_body_ids.append(p.id)

    game.state = GameState.MEETING
    game.active_meeting = MeetingState(
        started_at=time.time(),
        started_by=target.id,
        started_by_name=target.name,
        meeting_type="body_report"
    )

    alive_players = [{"id": p.id, "name": p.name} for p in game.get_alive_players()]
    dead_players = [{"id": p.id, "name": p.name} for p in game.get_dead_players()]

    await ws_manager.broadcast_to_game(game.code, {
        "type": "meeting_called",
        "payload": {
            "caller_id": target.id,
            "called_by": target.name,
            "meeting_type": "body_report",
            "phase": "gathering",
            "task_percentage": game.get_task_completion_percentage(),
            "alive_players": alive_players,
            "dead_players": dead_players,
            "enable_voting": game.settings.enable_voting,
            "anonymous_voting": game.settings.anonymous_voting,
            "timer_duration": game.settings.meeting_timer_duration,
            "warning_time": game.settings.meeting_warning_time
        }
    })

    return {"success": True}


@router.post("/games/{code}/ability/vulture-eat")
async def vulture_eat_endpoint(code: str, session_token: str, body_player_id: str):
    """Vulture: Eat a dead body to work toward win condition."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if player.role != Role.VULTURE:
        raise HTTPException(status_code=403, detail="Not a Vulture")

    if player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="You are dead")

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Cannot eat bodies now")

    body = game.players.get(body_player_id)
    if not body:
        raise HTTPException(status_code=404, detail="Player not found")

    if body.status != PlayerStatus.DEAD:
        raise HTTPException(status_code=400, detail="Player is not dead")

    # Prevent eating the same body twice
    if body_player_id in player.vulture_eaten_body_ids:
        raise HTTPException(status_code=400, detail="Already ate this body")

    # Prevent eating bodies discovered in meetings or voted out
    if body_player_id in game.vulture_ineligible_body_ids:
        raise HTTPException(status_code=400, detail="This body is no longer available")

    # Eat the body
    player.vulture_eaten_body_ids.append(body_player_id)
    player.vulture_bodies_eaten += 1
    bodies_needed = game.settings.vulture_eat_count

    # Notify the dead player they were eaten (private message)
    await ws_manager.send_to_player(game.code, body.id, {
        "type": "body_eaten",
        "payload": {
            "message": "A Vulture ate your body! Act alive until the next meeting."
        }
    })

    # Check vulture win condition
    if player.vulture_bodies_eaten >= bodies_needed:
        game.state = GameState.ENDED
        game.winner = "Vulture"
        game.active_sabotage = None  # Clear any active sabotage
        await ws_manager.broadcast_to_game(game.code, {
            "type": "game_ended",
            "payload": {
                "winner": "Vulture",
                "reason": f"{player.name} ate enough bodies!",
                "roles": get_all_roles(game)
            }
        })
        return {"success": True, "vulture_wins": True, "bodies_eaten": player.vulture_bodies_eaten, "bodies_needed": bodies_needed}

    return {
        "success": True,
        "bodies_eaten": player.vulture_bodies_eaten,
        "bodies_needed": bodies_needed
    }


@router.post("/games/{code}/ability/bounty-kill")
async def bounty_kill_endpoint(code: str, session_token: str, claimed: bool = True):
    """Rampager: Handle bounty target death. If claimed, increment kill count. Always reassigns target."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if player.role != Role.BOUNTY_HUNTER:
        raise HTTPException(status_code=403, detail="Not a Bounty Hunter")

    if player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="You are dead")

    if game.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in progress")

    # Verify current target is dead
    if not player.bounty_target_id:
        raise HTTPException(status_code=400, detail="No bounty target assigned")

    target = game.players.get(player.bounty_target_id)
    if not target or target.status != PlayerStatus.DEAD:
        raise HTTPException(status_code=400, detail="Bounty target is not dead")

    # Only increment bounty kills if player claimed the kill
    if claimed:
        player.bounty_kills += 1

    # Reassign to new target
    new_target_id = reassign_bounty_target(game, player)
    new_target_name = None
    if new_target_id:
        new_target = game.players.get(new_target_id)
        if new_target:
            new_target_name = new_target.name

    # Send updated target info privately
    await ws_manager.send_to_player(game.code, player.id, {
        "type": "bounty_target_update",
        "payload": {
            "target_id": new_target_id,
            "target_name": new_target_name,
            "bounty_kills": player.bounty_kills
        }
    })

    return {
        "success": True,
        "bounty_kills": player.bounty_kills,
        "new_target_id": new_target_id,
        "new_target_name": new_target_name
    }


@router.post("/games/{code}/ability/swapper-swap")
async def swapper_swap_endpoint(code: str, session_token: str, player1_id: str, player2_id: str):
    """Swapper: Select two players to swap all votes between them."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if player.role != Role.SWAPPER:
        raise HTTPException(status_code=403, detail="Not a Swapper")

    if player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="You are dead")

    if game.state != GameState.MEETING:
        raise HTTPException(status_code=400, detail="Can only swap during meetings")

    if game.active_meeting.phase != "voting":
        raise HTTPException(status_code=400, detail="Can only swap during voting phase")

    player1 = game.players.get(player1_id)
    player2 = game.players.get(player2_id)

    if not player1 or not player2:
        raise HTTPException(status_code=404, detail="Player not found")

    if player1.status != PlayerStatus.ALIVE or player2.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=400, detail="Can only swap votes for alive players")

    # Store swap targets - will be applied when votes are tallied
    player.swapper_targets = (player1_id, player2_id)

    return {
        "success": True,
        "swapped": [player1.name, player2.name],
        "message": f"Votes for {player1.name} and {player2.name} will be swapped!"
    }
