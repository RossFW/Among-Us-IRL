"""Shared async game helpers that bridge game logic and WebSocket notifications."""
from ..models import Role, PlayerStatus
from ..services.game_logic import reassign_bounty_target
from ..services.ws_manager import ws_manager


async def check_and_reassign_bounty_targets(game, dead_player_id: str):
    """If any alive Rampager has the dead player as their bounty target, reassign and notify."""
    for player in game.players.values():
        if (player.role == Role.BOUNTY_HUNTER
                and player.status == PlayerStatus.ALIVE
                and player.bounty_target_id == dead_player_id):
            new_target_id = reassign_bounty_target(game, player)
            new_target_name = None
            if new_target_id:
                new_target = game.players.get(new_target_id)
                if new_target:
                    new_target_name = new_target.name

            await ws_manager.send_to_player(game.code, player.id, {
                "type": "bounty_target_update",
                "payload": {
                    "target_id": new_target_id,
                    "target_name": new_target_name,
                    "bounty_kills": player.bounty_kills
                }
            })


async def check_executioner_fallback(game, dead_player_id: str):
    """If Executioner's target dies outside voting, convert Executioner to Jester."""
    for player in game.players.values():
        if (player.role == Role.EXECUTIONER
                and player.status == PlayerStatus.ALIVE
                and player.executioner_target_id == dead_player_id):
            player.role = Role.JESTER
            player.executioner_target_id = None
            await ws_manager.send_to_player(game.code, player.id, {
                "type": "role_changed",
                "payload": {
                    "new_role": "Jester",
                    "reason": "Your target died. You are now a Jester!"
                }
            })


async def check_lookout_notify(game, dead_player_id: str):
    """If any alive Lookout is watching the dead player, send them an alert (PLAYING state only)."""
    from ..models import GameState
    if game.state != GameState.PLAYING:
        return
    dead_player = game.players.get(dead_player_id)
    if not dead_player:
        return
    for player in game.players.values():
        if (player.role == Role.LOOKOUT
                and player.status == PlayerStatus.ALIVE
                and player.lookout_target_id == dead_player_id):
            await ws_manager.send_to_player(game.code, player.id, {
                "type": "lookout_alert",
                "payload": {
                    "target_name": dead_player.name,
                    "message": f"Your watched player {dead_player.name} has been killed!"
                }
            })
