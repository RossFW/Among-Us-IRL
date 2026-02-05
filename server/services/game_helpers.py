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
