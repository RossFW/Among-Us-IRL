"""Meeting and voting routes."""

from fastapi import APIRouter, HTTPException
from ..database import game_store
from ..models import GameState, PlayerStatus, Role, MeetingState, Vote, VoteType, ROLE_CATEGORIES, RoleCategory
import time
from ..services.ws_manager import ws_manager
from ..services.game_logic import check_win_conditions, get_role_info, get_all_roles, reassign_bounty_target
from ..services.game_helpers import check_and_reassign_bounty_targets

router = APIRouter(prefix="/api", tags=["meetings"])


@router.post("/games/{code}/meeting/start")
async def start_meeting_endpoint(code: str, session_token: str, meeting_type: str = "meeting"):
    """Call a meeting. meeting_type can be 'meeting' or 'body_report'."""
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

    # Initialize meeting state for voting
    game.active_meeting = MeetingState(
        started_at=time.time(),
        started_by=player.id,
        started_by_name=player.name,
        meeting_type=meeting_type,
        phase="gathering"  # Waiting for caller to start voting
    )

    # Mark all currently dead bodies as ineligible for vulture eating
    # Bodies from previous rounds are "discovered" when a meeting starts
    for p in game.players.values():
        if p.status == PlayerStatus.DEAD and p.id not in game.vulture_ineligible_body_ids:
            game.vulture_ineligible_body_ids.append(p.id)

    # Handle active sabotage during meeting
    # Reactor and O2 resolve on meeting, Lights persists
    sabotage_resolved = None
    if game.active_sabotage is not None:
        sab = game.active_sabotage
        if sab.type in ["reactor", "o2"]:
            # Resolve sabotage
            sabotage_resolved = {
                "type": sab.type,
                "name": sab.name,
                "reason": "Meeting called"
            }
            game.active_sabotage = None
            # Set cooldown
            game.sabotage_cooldown_end = time.time() + game.settings.sabotage_cooldown

        # Lights persists through meetings - don't clear it

    # Broadcast meeting start (gathering phase - waiting for caller to start voting)
    await ws_manager.broadcast_to_game(game.code, {
        "type": "meeting_called",
        "payload": {
            "called_by": player.name,
            "caller_id": player.id,  # So frontend knows who can start voting
            "meeting_type": meeting_type,  # "meeting" or "body_report"
            "phase": "gathering",  # Waiting phase
            "task_percentage": game.get_task_completion_percentage(),
            "alive_players": [
                {"id": p.id, "name": p.name}
                for p in game.get_alive_players()
            ],
            "dead_players": [
                {"id": p.id, "name": p.name}
                for p in game.get_dead_players()
            ],
            # Voting settings
            "enable_voting": game.settings.enable_voting,
            "anonymous_voting": game.settings.anonymous_voting,
            "timer_duration": game.settings.meeting_timer_duration,
            "warning_time": game.settings.meeting_warning_time
        }
    })

    # If sabotage was resolved by meeting, broadcast that too
    if sabotage_resolved:
        await ws_manager.broadcast_to_game(game.code, {
            "type": "sabotage_resolved",
            "payload": {
                "type": sabotage_resolved["type"],
                "name": sabotage_resolved["name"],
                "resolved_by": "Meeting",
                "message": f"{sabotage_resolved['name']} resolved by meeting"
            }
        })

    return {"success": True}


@router.post("/games/{code}/meeting/start_voting")
async def start_voting_endpoint(code: str, session_token: str):
    """Start the voting phase of a meeting. Only the caller can do this."""
    game = game_store.get_game(code.upper())
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if game.state != GameState.MEETING or not game.active_meeting:
        raise HTTPException(status_code=400, detail="No meeting in progress")

    # Verify this is the caller
    player = game.get_player_by_session(session_token)
    if not player or player.id != game.active_meeting.started_by:
        raise HTTPException(status_code=403, detail="Only the meeting caller can start voting")

    if game.active_meeting.phase == "voting":
        return {"success": True, "already_started": True}

    # Transition to voting phase
    game.active_meeting.phase = "voting"

    # Set server-side timestamps for validation
    now = time.time()
    discussion_time = game.settings.discussion_time or 0
    timer_duration = game.settings.meeting_timer_duration or 120

    game.active_meeting.discussion_end_time = now + discussion_time
    game.active_meeting.voting_end_time = now + timer_duration

    # Broadcast voting started to everyone
    await ws_manager.broadcast_to_game(game.code, {
        "type": "voting_started",
        "payload": {
            "alive_players": [
                {"id": p.id, "name": p.name}
                for p in game.get_alive_players()
            ],
            "enable_voting": game.settings.enable_voting,
            "anonymous_voting": game.settings.anonymous_voting,
            "timer_duration": game.settings.meeting_timer_duration,
            "warning_time": game.settings.meeting_warning_time,
            "discussion_time": game.settings.discussion_time
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

    # Reset guesser state for next meeting
    for player in game.players.values():
        if player.role in [Role.NICE_GUESSER, Role.EVIL_GUESSER]:
            player.guesser_used_this_meeting = False

    # Clear active meeting state
    game.active_meeting = None
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
        game.active_sabotage = None
        await ws_manager.broadcast_to_game(game.code, {
            "type": "game_ended",
            "payload": {
                "winner": winner,
                "roles": get_all_roles(game)
            }
        })

    return {"success": True}


@router.post("/games/{code}/vote")
async def cast_vote_endpoint(code: str, session_token: str, target_id: str = None):
    """Cast a vote during a meeting. target_id=None means skip vote."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if game.state != GameState.MEETING:
        raise HTTPException(status_code=400, detail="No meeting in progress")

    if not game.active_meeting:
        raise HTTPException(status_code=400, detail="Meeting state not initialized")

    # Phase validation - must be in voting phase
    if game.active_meeting.phase != "voting":
        raise HTTPException(status_code=400, detail="Voting has not started yet")

    # Discussion time validation - must be over
    if game.active_meeting.discussion_end_time and time.time() < game.active_meeting.discussion_end_time:
        raise HTTPException(status_code=400, detail="Discussion time is not over yet")

    if player.status != PlayerStatus.ALIVE:
        raise HTTPException(status_code=403, detail="Dead players cannot vote")

    if player.id in game.active_meeting.votes:
        raise HTTPException(status_code=400, detail="Already voted")

    # Validate target if not skip
    if target_id:
        target = game.players.get(target_id)
        if not target:
            raise HTTPException(status_code=400, detail="Invalid target")
        if target.status != PlayerStatus.ALIVE:
            raise HTTPException(status_code=400, detail="Cannot vote for dead player")
        # Self-voting is allowed (Jester strategy!)

    # Create vote
    vote = Vote(
        voter_id=player.id,
        target_id=target_id,
        vote_type=VoteType.PLAYER if target_id else VoteType.SKIP,
        timestamp=time.time()
    )
    game.active_meeting.votes[player.id] = vote

    # Count votes
    alive_players = game.get_alive_players()
    votes_cast = len(game.active_meeting.votes)
    votes_needed = len(alive_players)
    all_voted = votes_cast >= votes_needed

    # Broadcast vote cast
    # Debug: log anonymous_voting value and type
    print(f"DEBUG vote_cast: anonymous_voting={game.settings.anonymous_voting} (type={type(game.settings.anonymous_voting).__name__}), voter={player.name}, target_id={target_id}")
    print(f"DEBUG: condition 'not anonymous_voting' evaluates to: {not game.settings.anonymous_voting}")

    await ws_manager.broadcast_to_game(game.code, {
        "type": "vote_cast",
        "payload": {
            "votes_cast": votes_cast,
            "votes_needed": votes_needed,
            "all_voted": all_voted,
            # Include voter info only if not anonymous
            "voter_name": player.name if not game.settings.anonymous_voting else None,
            "target_name": (game.players.get(target_id).name if target_id else "Skip") if not game.settings.anonymous_voting else None
        }
    })

    # If all voted, reveal results
    if all_voted:
        await reveal_vote_results(game)

    return {"success": True, "votes_cast": votes_cast, "all_voted": all_voted}


@router.post("/games/{code}/meeting/timer_expired")
async def meeting_timer_expired_endpoint(code: str, session_token: str):
    """Called when meeting timer expires - trigger vote results."""
    result = game_store.get_player_by_session(session_token)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")

    game, player = result

    if game.state != GameState.MEETING or not game.active_meeting:
        raise HTTPException(status_code=400, detail="No meeting in progress")

    if game.active_meeting.voting_ended:
        return {"success": True, "already_ended": True}

    await reveal_vote_results(game)
    return {"success": True}


async def reveal_vote_results(game):
    """Calculate and broadcast vote results, then eliminate if needed."""
    if game.active_meeting.voting_ended:
        return

    game.active_meeting.voting_ended = True

    # Check for Swapper - apply vote swaps
    swapper_targets = None
    for p in game.players.values():
        if p.role == Role.SWAPPER and p.swapper_targets and p.status == PlayerStatus.ALIVE:
            swapper_targets = p.swapper_targets
            # Reset for next meeting
            p.swapper_targets = None
            break

    # Count votes with special role handling
    vote_counts = {}  # player_id -> count
    skip_count = 0

    for vote in game.active_meeting.votes.values():
        voter = game.players.get(vote.voter_id)
        # Mayor's vote counts twice
        weight = 2 if voter and voter.role == Role.MAYOR else 1

        target_id = vote.target_id

        # Apply Swapper's swap
        if swapper_targets and target_id:
            p1, p2 = swapper_targets
            if target_id == p1:
                target_id = p2
            elif target_id == p2:
                target_id = p1

        if vote.vote_type == VoteType.SKIP or not target_id:
            skip_count += weight
        else:
            vote_counts[target_id] = vote_counts.get(target_id, 0) + weight

    # Find max votes
    all_counts = [skip_count] + list(vote_counts.values())
    max_votes = max(all_counts) if all_counts else 0

    # Determine outcome
    candidates = [pid for pid, count in vote_counts.items() if count == max_votes]
    skip_is_max = skip_count == max_votes

    result = {
        "vote_counts": {
            game.players[pid].name: count
            for pid, count in vote_counts.items()
        },
        "skip_count": skip_count,
        "total_votes": len(game.active_meeting.votes)
    }

    # Track swapped player names for display
    swapped_names = []
    if swapper_targets:
        p1 = game.players.get(swapper_targets[0])
        p2 = game.players.get(swapper_targets[1])
        if p1:
            swapped_names.append(p1.name)
        if p2:
            swapped_names.append(p2.name)
        # Ensure both swapped players appear in vote_counts even with 0 votes
        for name in swapped_names:
            if name not in result["vote_counts"]:
                result["vote_counts"][name] = 0
    result["swapped_names"] = swapped_names

    eliminated_player = None

    if len(candidates) == 0 or (len(candidates) == 1 and skip_is_max and skip_count >= vote_counts.get(candidates[0], 0)):
        # Skip won or no votes for players
        result["outcome"] = "skip"
        result["eliminated"] = None
    elif len(candidates) > 1 or (len(candidates) == 1 and skip_is_max):
        # Tie between players or player tied with skip
        result["outcome"] = "tie"
        result["eliminated"] = None
    else:
        # Someone is eliminated
        eliminated_id = candidates[0]
        eliminated_player = game.players.get(eliminated_id)
        result["outcome"] = "elimination"
        result["eliminated"] = eliminated_id
        result["eliminated_name"] = eliminated_player.name
        result["eliminated_role"] = eliminated_player.role.value if eliminated_player.role else None

    # Add individual votes if non-anonymous voting
    # Debug logging
    print(f"DEBUG vote_results: anonymous_voting={game.settings.anonymous_voting}")

    if not game.settings.anonymous_voting:
        # Group voters by target for cleaner display
        votes_by_target = {}  # target_name -> list of voter names
        for vote in game.active_meeting.votes.values():
            target_name = game.players[vote.target_id].name if vote.target_id else "Skip"
            voter = game.players.get(vote.voter_id)
            voter_name = voter.name if voter else "Unknown"
            if target_name not in votes_by_target:
                votes_by_target[target_name] = []
            # Mayor's vote counts twice - show their name twice
            if voter and voter.role == Role.MAYOR:
                votes_by_target[target_name].append(voter_name)
                votes_by_target[target_name].append(voter_name)
            else:
                votes_by_target[target_name].append(voter_name)

        result["votes_by_target"] = votes_by_target
        print(f"DEBUG votes_by_target: {votes_by_target}")

        # Also keep flat list for backwards compatibility
        result["individual_votes"] = [
            {
                "voter_name": game.players[vote.voter_id].name,
                "target_name": game.players[vote.target_id].name if vote.target_id else "Skip"
            }
            for vote in game.active_meeting.votes.values()
        ]

    game.active_meeting.result = result

    # Broadcast results
    await ws_manager.broadcast_to_game(game.code, {
        "type": "vote_results",
        "payload": result
    })

    # Handle elimination
    if eliminated_player:
        eliminated_player.status = PlayerStatus.DEAD

        # Voted-out players are ineligible for vulture eating
        if eliminated_player.id not in game.vulture_ineligible_body_ids:
            game.vulture_ineligible_body_ids.append(eliminated_player.id)

        # Notify everyone that this player died (so their UI updates)
        await ws_manager.broadcast_to_game(game.code, {
            "type": "player_died",
            "payload": {
                "player_id": eliminated_player.id,
                "name": eliminated_player.name,
                "cause": "voted_out"
            }
        })

        # Auto-reassign bounty targets if the eliminated player was someone's target
        await check_and_reassign_bounty_targets(game, eliminated_player.id)

        # Check for Jester win
        if eliminated_player.role == Role.JESTER:
            game.state = GameState.ENDED
            game.winner = "Jester"
            game.active_sabotage = None
            await ws_manager.broadcast_to_game(game.code, {
                "type": "game_ended",
                "payload": {
                    "winner": "Jester",
                    "reason": f"{eliminated_player.name} was the Jester!",
                    "roles": get_all_roles(game)
                }
            })
            return

        # Check other win conditions
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
