# Testing Checklist - Post-Refactor Verification

**Date Started:** 2026-02-05
**Commit:** c0c0fb3 (JS extraction + route split)
**Automated Tests:** ✅ 100+ tests implemented (see [TEST_README.md](TEST_README.md))

## 🤖 Automated Testing

**Quick Start:**
```bash
python test_game_flow.py all    # Run all automated tests
```

**See [TEST_README.md](TEST_README.md) for full testing documentation.**

### Automated Test Coverage:
- ✅ **Basic Flow** (21 tests): Lobby, game start, tasks, meetings, sabotage
- ✅ **Voting Scenarios** (81 tests): All voting outcomes, ties, plurality
- ✅ **Role Abilities** (varies): Engineer, Captain, Sheriff abilities
- ✅ **Sabotage** (varies): Lights persistence, cooldowns
- ✅ **Edge Cases** (varies): Dead players, invalid operations, ghost tasks
- ✅ **Slot-Based Roles** (`slots`): Default settings, neutrals, advanced crew, full pipeline
- ✅ **Executioner** (`executioner`): Target assignment, win on vote out, Jester fallback
- ✅ **Lookout** (`lookout`): Player selection, self-watch rejection, post-meeting constraints

**New test commands:**
```bash
python test_game_flow.py slots        # Slot-based role assignment
python test_game_flow.py executioner  # Executioner mechanics
python test_game_flow.py lookout      # Lookout mechanics
python test_game_flow.py new          # All new tests (slots + executioner + lookout)
```

---

## 📋 Manual Testing Checklist

Use this checklist for manual verification of features that require human testing (UI/UX, complex interactions, IRL mechanics).

### Status Icons:
- ✅ = Verified working
- ❌ = Broken/needs fix
- ⚠️ = Partial/needs review
- 🤖 = Automated test covers this
- ⏭️ = Skipped/not applicable

---

## Basic Game Flow
- [ ] Create game (home page loads, creates 4-letter code)
- [ ] Join game (multiple players can join with code)
- [ ] Lobby settings UI works (toggle switches, sliders, dropdowns)
- [ ] Start game (roles assigned, role reveal screen)
- [ ] WebSocket connection stays alive (check for disconnects)

---

## Frontend JS - Core (game-core.js)
- [ ] Settings UI updates correctly (all toggles, probabilities)
- [ ] State sync works on page load/reconnect
- [ ] Task completion/incompletion updates progress bar
- [ ] Game end screen shows all roles correctly
- [ ] Return to lobby works
- [ ] Sound effects play (role reveal, meeting, etc.)

---

## Frontend JS - Meetings (game-meeting.js)
- [ ] Call meeting button works
- [ ] Report body button works
- [ ] Meeting gathering phase → voting phase transition
- [ ] Vote buttons appear for all alive players
- [ ] Vote casting works (shows "Voted" state)
- [ ] Vote results display correctly (tallies, tied/skip)
- [ ] Anonymous voting toggle works
- [ ] **Guesser modal**: opens, role selection works, guess submits
- [ ] **Swapper UI**: swap vote interface works during voting
- [ ] Meeting cooldown timer displays correctly

---

## Frontend JS - Abilities (game-abilities.js)
- [ ] Task toggle works (checkboxes)
- [ ] **Engineer**: remote fix button appears & works
- [ ] **Captain**: remote meeting button appears & works
- [ ] **Bounty Hunter**: kill claim button works, cooldown timer shows
- [ ] **Vulture**: body list populates, eat body works
- [ ] **Noise Maker**: death triggers target selection modal
- [ ] Kill cooldown timer (Impostor/Sheriff/Lone Wolf) displays & counts down
- [ ] Jester voted out triggers win (tested from meeting results)

---

## Frontend JS - Sabotage (game-sabotage.js)
- [ ] Impostor sabotage panel shows when sabotage enabled
- [ ] Sabotage buttons enable/disable based on cooldown
- [ ] Start sabotage works (Lights, Reactor, O2, Comms)
- [ ] Sabotage cooldown timer displays correctly
- [ ] Fix sabotage button appears for crewmates
- [ ] Reactor: 2-person hold mechanic works
- [ ] O2: 2-switch flip mechanic works
- [ ] Sabotage timer countdown (Reactor/O2) shows and updates

---

## Backend Routes - Game (game.py)
- [ ] POST `/api/games/{code}/start` — Start game
- [ ] POST `/api/games/{code}/end` — End game
- [ ] POST `/api/games/{code}/complete_task` — Task completion
- [ ] POST `/api/games/{code}/uncomplete_task` — Task incompletion
- [ ] POST `/api/games/{code}/players/{id}/die` — Mark dead
- [ ] POST `/api/games/{code}/players/{id}/jester-win` — Jester win
- [ ] POST `/api/games/{code}/sheriff/shoot/{target}` — Sheriff shoot
- [ ] GET `/api/games/{code}/players/me` — Get player info
- [ ] GET `/api/games/{code}/role_guide` — Role guide data

---

## Backend Routes - Meetings (meetings.py)
- [ ] POST `/api/games/{code}/meeting/start` — Call meeting/report body
- [ ] POST `/api/games/{code}/meeting/start_voting` — Begin voting phase
- [ ] POST `/api/games/{code}/vote` — Cast vote
- [ ] POST `/api/games/{code}/meeting/timer_expired` — Timer expiry
- [ ] POST `/api/games/{code}/meeting/end` — End meeting
- [ ] Vote tallying logic (Mayor 2x votes, ties, skips)
- [ ] Jester win condition triggers when voted out

---

## Backend Routes - Abilities (abilities.py)
- [ ] POST `/api/games/{code}/ability/engineer-fix` — Engineer remote fix
- [ ] POST `/api/games/{code}/ability/captain-meeting` — Captain remote meeting
- [ ] POST `/api/games/{code}/ability/guesser-guess` — Guesser role guess (correct/wrong)
- [ ] POST `/api/games/{code}/ability/noise-maker-select` — Noise maker target
- [ ] POST `/api/games/{code}/ability/vulture-eat` — Vulture eat body (win check)
- [ ] POST `/api/games/{code}/ability/bounty-kill` — Bounty Hunter kill claim
- [ ] POST `/api/games/{code}/ability/swapper-swap` — Swapper vote swap
- [ ] POST `/api/games/{code}/ability/lookout-select` — Lookout watch target

---

## Backend Routes - Sabotage (sabotage.py)
- [ ] POST `/api/games/{code}/sabotage/start` — Trigger sabotage
- [ ] POST `/api/games/{code}/sabotage/fix` — Fix sabotage
- [ ] POST `/api/games/{code}/sabotage/check_timeout` — Timeout check
- [ ] GET `/api/games/{code}/sabotage/status` — Sabotage status

---

## Slot-Based Role Assignment
- [ ] **Neutrals counter** in lobby settings (+/- buttons work)
- [ ] **Advanced Crew counter** in lobby settings (+/- buttons work)
- [ ] All role toggles use unified system (no legacy toggle/config split)
- [ ] Setting num_neutrals=1 + enabling Jester → Jester assigned
- [ ] Setting num_advanced_crew=2 + enabling Sheriff/Engineer → both assigned
- [ ] More slots than enabled roles → unfilled slots become Crewmate
- [ ] Auto-adjust when total slots > player count

## New Roles
- [ ] **Executioner**: Target display shows crew player name
- [ ] **Executioner**: Target voted out + Executioner voted for target → Executioner wins
- [ ] **Executioner**: Target dies non-vote → Executioner becomes Jester (role_changed WS)
- [ ] **Executioner**: Role changed notification displays in UI
- [ ] **Lookout**: Selection modal shows players alive at last meeting
- [ ] **Lookout**: Selecting a player updates "WATCHING" display
- [ ] **Lookout**: Watched player killed outside meeting → popup overlay appears
- [ ] **Lookout**: Watched player voted out in meeting → NO popup
- [ ] **Lookout**: Popup has DISMISS button that closes it
- [ ] **Lookout**: Cannot watch themselves (rejected)

## Integration & Edge Cases
- [ ] **Bounty target reassignment**: Target dies in meeting → new target assigned
- [ ] **Role constants**: All 5 constants load correctly (sabotage panel, tasks, etc.)
- [ ] **Service worker**: New JS files cached (check Network tab)
- [ ] Win conditions (crew task victory, impostor majority, jester, lone wolf, vulture, executioner)
- [ ] Multiple games can run simultaneously (different codes)
- [ ] Page refresh/reconnect restores correct state

---

## Known Issues / Notes
- **Captain remote meeting**: ⚠️ Can't call if already used (expected behavior?)

---

## Test Coverage Summary
- **Total items:** ~80
- **Completed:** ___ / 80
- **Issues found:** ___
