# Among Us IRL - Project Overview

## What Is This?

A **Progressive Web App (PWA)** for playing Among Us in real life at an ice cream factory. Players use their phones as game companions — seeing their role, tracking tasks, calling meetings, voting, and using special abilities. All social interaction happens in person; the app handles game state.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI 0.109.0 |
| Real-time | WebSockets (native FastAPI) |
| Templates | Jinja2 (server-side rendered) |
| Frontend | Vanilla JavaScript, HTML5, CSS3 (no frameworks) |
| State | In-memory dict (no persistence — server restart = games lost) |
| PWA | Service Worker, manifest.json (installable, offline-capable) |
| Server | Uvicorn 0.27.0 with `--reload` for dev |
| External Access | Cloudflare Tunnel (quick tunnels, no account needed) |

## How to Run

```bash
# Activate venv
cd among-us-pwa
source venv/bin/activate

# Local only
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload

# With public URL for phones
python run.py --tunnel

# Test mode (auto-create/join game on 5 devices)
# Navigate to /test on each device — first creates game, rest auto-join
```

## Architecture

```
among-us-pwa/
├── run.py                     # Startup script (server + optional tunnel)
├── server/
│   ├── main.py                # FastAPI app, route registration, page serving
│   ├── models.py              # All data models, enums, 18 roles, settings (~530 lines)
│   ├── database.py            # In-memory GameStore (dict of code → GameModel)
│   ├── routes/
│   │   ├── lobby.py           # Create/join game, settings, tasks, test mode
│   │   ├── game.py            # Core gameplay: start, kill, meetings, voting, abilities (~1260 lines)
│   │   └── websocket.py       # WS connection, state sync, reconnection
│   ├── services/
│   │   ├── game_logic.py      # Role assignment, task distribution, win conditions (~480 lines)
│   │   └── ws_manager.py      # WebSocket broadcast/send manager
│   └── templates/
│       ├── base.html          # PWA shell (manifest, service worker, icons)
│       └── pages/
│           ├── home.html      # Create/join game screen
│           ├── game.html      # Main game UI — lobby, gameplay, meetings, voting (~2600 lines)
│           └── test_redirect.html  # Test mode auto-join
├── static/
│   ├── css/styles.css         # All styling (~35KB)
│   ├── js/app.js              # PWA service worker registration
│   ├── sw.js                  # Service Worker
│   ├── icons/                 # PWA icons
│   ├── images/maps/           # Game map images
│   └── sounds/                # Sound effects (role reveal, meetings, voting, sabotage, win)
```

### Key Files

- **server/models.py** — Single source of truth for all data structures. Contains `GameModel`, `PlayerModel`, `GameSettings`, `MeetingState`, `ActiveSabotage`, all 18 `Role` enum values, `ROLE_CATEGORIES` mapping, and `ROLE_DESCRIPTIONS`.
- **server/routes/game.py** — Largest file. All gameplay endpoints: start game, die, meetings, voting, sabotage, and every role ability endpoint.
- **server/services/game_logic.py** — Pure logic: `assign_roles()` (probability-based), `distribute_tasks()`, `check_win_conditions()`, `sheriff_shoot()`, `get_role_info()`.
- **server/templates/pages/game.html** — Monolithic frontend. All screens (lobby, game, meeting, death) in one file with inline JavaScript.

### State Management

All game state lives in `GameStore.games` (a Python dict). No database. Server restart wipes everything. Players are identified by `session_token` (UUID stored in localStorage). WebSocket connections enable real-time broadcasts.

### Real-time Communication

WebSocket at `/ws/{game_code}/{session_token}`. On connect, server sends full `state_sync` including game state, role info, active sabotage, and active meeting. All game events broadcast via `ws_manager.broadcast_to_game()` or `ws_manager.send_to_player()`.

## Game Flow

```
CREATE GAME → 4-letter code generated
     ↓
JOIN GAME → Players enter code on their phones
     ↓
LOBBY → Host configures settings (tasks, roles, sabotage, voting)
     ↓
START GAME → Roles assigned, tasks distributed, role reveal sound
     ↓
PLAYING → Crewmates do tasks, impostors kill, special abilities active
     ↓
MEETING → Called by button or body report → gathering → voting → results
     ↓
WIN CHECK → After kills, votes, tasks, or vulture eats
     ↓
GAME ENDED → All roles revealed, winner announced
```

## Roles (18 Total)

### Crew-Aligned (8)
| Role | Ability |
|------|---------|
| **Crewmate** | Complete tasks, vote out impostors |
| **Sheriff** | Shoot a player — hit impostor = they die, hit crew = YOU die |
| **Engineer** | Fix one sabotage remotely per game (from anywhere) |
| **Captain** | Call one remote meeting per game (from anywhere) |
| **Mayor** | Vote counts as 2 votes |
| **Nice Guesser** | Guess a player's role during voting — correct = they die, wrong = you die |
| **Spy** | Appears as impostor to impostors (undercover crew) |
| **Swapper** | Swap votes between two players during voting. Can't call meetings or fix Lights |

### Impostor-Aligned (5)
| Role | Ability |
|------|---------|
| **Impostor** | Kill crewmates, trigger sabotage |
| **Evil Guesser** | Same as Nice Guesser but for impostor team |
| **Bounty Hunter** | Faster kill cooldown on designated target, slower on others |
| **Cleaner** | "Clean" dead bodies (tell dead player to act alive until next meeting) |
| **Venter** | Can go outside / through vents (access doors) |

### Neutral (4)
| Role | Win Condition |
|------|---------------|
| **Jester** | Get voted out during a meeting |
| **Lone Wolf** | Be the last one standing (kill everyone) |
| **Vulture** | Eat X dead bodies before game ends |
| **Noise Maker** | When killed, choose who gets a fake "body found" notification |

### Special: Minion
Impostor-aligned but categorized as crew in appearance. Wins with impostors but doesn't know who they are. Blind — acts like crew.

### Role Configuration
Legacy roles (Jester, Lone Wolf, Minion, Sheriff) use simple on/off toggles. New roles use probability-based config: `enabled`, `probability` (0-100%), `max_count`.

## Sabotage System

4 configurable sabotage types (impostors only):
1. **Lights** — No timer, persists after meetings, one-tap fix
2. **Reactor** — Countdown timer, needs 2 people holding simultaneously
3. **O2** — Countdown timer, needs 2 switches flipped collectively
4. **Comms** — Customizable (placeholder)

Each has: custom name, enable toggle, timer (0 = no countdown). Global cooldown between sabotages. Timer expiry = impostor win. Engineer can fix one remotely.

## Meeting & Voting System

### Phases
1. **Gathering** — Meeting called (by button, body report, or Captain ability). Players assemble IRL. Caller sees START VOTING button.
2. **Voting** — Discussion time countdown, then vote buttons appear. Each alive player votes for a player or skips. Mayor's vote = 2x. Swapper can swap vote targets.
3. **Results** — Vote tallies shown. Most votes = eliminated (ties = no elimination). Jester voted out = Jester wins.

### Settings
- Meeting timer duration (30-300s, default 120s)
- Warning sound time (before timer ends)
- Discussion time before voting (0+s, default 5s)
- Anonymous voting toggle
- Enable/disable voting entirely

## Win Conditions

- **Crewmate** — All tasks complete OR all impostors dead (and no Lone Wolf)
- **Impostor** — Impostors ≥ non-impostors (and no Lone Wolf)
- **Jester** — Gets voted out
- **Lone Wolf** — Last alive with 1 crewmate, or sole survivor
- **Vulture** — Eats enough bodies (configurable threshold)
- Last 1 player alive → their team wins

## API Endpoints Summary

### Lobby
- `POST /api/games` — Create game
- `POST /api/games/{code}/join` — Join game
- `GET /api/games/{code}` — Get game state
- `PATCH /api/games/{code}/settings` — Update settings (host)
- `POST /api/games/{code}/tasks` — Add task
- `DELETE /api/games/{code}/tasks/{name}` — Remove task
- `POST /api/reconnect` — Reconnect session
- `POST /api/games/{code}/leave` — Leave game
- `POST /api/test/join` — Test mode: atomic create-or-join

### Gameplay
- `POST /api/games/{code}/start` — Start game
- `POST /api/games/{code}/end` — End game
- `POST /api/games/{code}/players/{id}/die` — Mark dead
- `GET /api/games/{code}/players/me` — Get own role/tasks

### Meetings & Voting
- `POST /api/games/{code}/meeting/start` — Call meeting
- `POST /api/games/{code}/meeting/start_voting` — Begin voting
- `POST /api/games/{code}/meeting/end` — End meeting
- `POST /api/games/{code}/vote` — Cast vote
- `POST /api/games/{code}/meeting/timer_expired` — Timer expired

### Sabotage
- `POST /api/games/{code}/sabotage/start` — Trigger sabotage
- `POST /api/games/{code}/sabotage/fix` — Fix sabotage
- `POST /api/games/{code}/sabotage/check_timeout` — Check timer
- `GET /api/games/{code}/sabotage/status` — Get status

### Role Abilities
- `POST /api/games/{code}/ability/engineer-fix` — Remote fix
- `POST /api/games/{code}/ability/captain-meeting` — Remote meeting
- `POST /api/games/{code}/ability/guesser-guess` — Guess role
- `POST /api/games/{code}/ability/vulture-eat` — Eat body
- `POST /api/games/{code}/ability/swapper-swap` — Swap votes
- `POST /api/games/{code}/sheriff/shoot/{target}` — Sheriff shoot
- `POST /api/games/{code}/players/{id}/jester-win` — Jester claim

## WebSocket Messages

| Message Type | Direction | Description |
|-------------|-----------|-------------|
| `state_sync` | Server→Client | Full state on connect/reconnect |
| `player_joined` / `player_left` | Broadcast | Lobby changes |
| `game_started` / `game_ended` | Broadcast | Game lifecycle |
| `player_died` | Broadcast | Death notification |
| `task_completed` | Broadcast | Task progress update |
| `meeting_called` | Broadcast | Meeting triggered |
| `voting_started` | Broadcast | Voting phase begins |
| `vote_cast` | Broadcast | Vote submitted |
| `vote_results` | Broadcast | Voting outcome |
| `meeting_ended` | Broadcast | Return to game |
| `sabotage_started` / `sabotage_resolved` | Broadcast | Sabotage events |
| `body_eaten` | Private | Vulture ate your body |
| `guesser_result` | Broadcast | Guesser guess outcome |
| `settings_changed` | Broadcast | Host changed settings |

## Known Architectural Notes

- **No persistence** — Everything in memory. Intentional for simplicity. Games are ephemeral.
- **Single-file frontend** — `game.html` is ~2600 lines with inline JS. Works but large.
- **Hot reload** — `--reload` mode watches all files. Any file save restarts server and wipes games. Be careful during live testing.
- **Session tokens** — UUIDs in localStorage. No user accounts. Anonymous play.
- **Asyncio safety** — Game state mutations happen synchronously (no `await` between read and write), preventing race conditions despite async handlers.
