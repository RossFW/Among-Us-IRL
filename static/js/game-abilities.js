// game-abilities.js - Role abilities, cooldowns, tasks

async function toggleTask(taskId) {
    const taskEl = document.querySelector(`.task-item[data-id="${taskId}"]`);
    if (!taskEl) return;

    const isCompleted = taskEl.classList.contains('completed');

    // Crew-aligned roles (except Minion) have real tasks that update the server
    if (REAL_TASK_ROLES.includes(myRole)) {
        const endpoint = isCompleted ? 'uncomplete' : 'complete';
        try {
            const response = await fetch(`/api/tasks/${taskId}/${endpoint}?session_token=${sessionToken}`, {
                method: 'POST'
            });

            if (response.ok) {
                toggleTaskUI(taskEl, isCompleted);
            }
        } catch (e) {
            console.error('Failed to toggle task:', e);
        }
    } else {
        // For other roles (Impostor, Jester, etc.), just toggle UI locally (fake tasks)
        toggleTaskUI(taskEl, isCompleted);
    }
}

function toggleTaskUI(taskEl, wasCompleted) {
    if (wasCompleted) {
        taskEl.classList.remove('completed');
        taskEl.querySelector('.task-check').textContent = '';
    } else {
        taskEl.classList.add('completed');
        taskEl.querySelector('.task-check').textContent = '\u2713';
    }
}

async function jesterVotedOut() {
    if (!confirm('Did you get voted out? This will end the game with a Jester victory!')) return;

    try {
        await fetch(`/api/players/${playerId}/jester-win?session_token=${sessionToken}`, {
            method: 'POST'
        });

        document.getElementById('jester-voted-btn').disabled = true;
        document.getElementById('jester-voted-btn').textContent = 'JESTER WINS!';
    } catch (e) {
        showError('Failed to claim victory');
    }
}

async function markDead() {
    if (!confirm('Are you sure you want to mark yourself as dead?')) return;

    try {
        const resp = await fetch(`/api/players/${playerId}/die?session_token=${sessionToken}`, {
            method: 'POST'
        });
        const data = await resp.json();

        document.getElementById('im-dead-btn').disabled = true;
        document.getElementById('im-dead-btn').textContent = 'YOU ARE DEAD';
        const deadMeetingBtn = document.getElementById('call-meeting-btn');
        deadMeetingBtn.disabled = true;
        deadMeetingBtn.textContent = 'YOU ARE DEAD';
        deadMeetingBtn.className = 'btn btn-secondary';
        document.getElementById('report-body-btn').disabled = true;

        // Noise Maker: show target selection modal
        if (data.noise_maker) {
            showNoiseMakerSelect();
        }
    } catch (e) {
        showError('Failed to mark as dead');
    }
}

// ==================== ROLE ABILITY FUNCTIONS ====================

function updateEngineerButton() {
    const btn = document.getElementById('engineer-fix-btn');
    if (!btn || btn.style.display === 'none') return;
    // Don't update if already used
    if (btn.textContent === 'FIX USED') return;

    if (activeSabotage) {
        btn.disabled = false;
        btn.textContent = 'FIX SABOTAGE REMOTELY';
    } else {
        btn.disabled = true;
        btn.textContent = 'NO ACTIVE SABOTAGE';
    }
}

async function engineerFix() {
    const btn = document.getElementById('engineer-fix-btn');
    if (btn.disabled) return;

    if (!confirm('Use your ONE remote fix to resolve the active sabotage?')) return;

    btn.disabled = true;
    try {
        const response = await fetch(`/api/games/${gameCode}/ability/engineer-fix?session_token=${sessionToken}`, {
            method: 'POST'
        });
        if (response.ok) {
            btn.textContent = 'FIX USED';
        } else {
            const data = await response.json();
            showError(data.detail || 'Failed to fix sabotage');
            btn.disabled = false;
        }
    } catch (e) {
        showError('Failed to fix sabotage');
        btn.disabled = false;
    }
}

async function captainMeeting() {
    const btn = document.getElementById('captain-meeting-btn');
    if (btn.disabled) return;

    // Check if sabotage is active
    if (activeSabotage) {
        showError('Cannot call meeting during sabotage!');
        return;
    }

    // Respect meeting cooldown (button already shows countdown via updateCaptainButtonCooldown)
    if (meetingCooldownEnd && Date.now() < meetingCooldownEnd) {
        return;
    }

    btn.disabled = true;
    try {
        const response = await fetch(`/api/games/${gameCode}/ability/captain-meeting?session_token=${sessionToken}`, {
            method: 'POST'
        });
        if (response.ok) {
            btn.textContent = 'REMOTE MEETING USED';
        } else {
            const data = await response.json();
            showError(data.detail || 'Failed to call meeting');
            btn.disabled = false;
        }
    } catch (e) {
        showError('Failed to call meeting');
        btn.disabled = false;
    }
}

// ==================== RAMPAGER ====================

function updateBountyKillButton() {
    const section = document.getElementById('bounty-hunter-section');
    if (!section || section.style.display === 'none') return;

    const wasItYou = document.getElementById('bounty-was-it-you');
    const killsDisplay = document.getElementById('bounty-kills-display');

    // Update kills counter
    if (killsDisplay) {
        killsDisplay.textContent = bountyKills > 0 ? `${bountyKills} bounty kill${bountyKills !== 1 ? 's' : ''}` : '';
    }

    if (!bountyTargetId) {
        wasItYou.style.display = 'none';
        return;
    }

    const target = allPlayers.find(p => p.id === bountyTargetId);
    if (target && target.status === 'dead') {
        // Target died! Show "Was it you?" prompt
        wasItYou.style.display = 'block';
        document.getElementById('bounty-prompt-text').textContent =
            `Your target ${target.name} is dead! Was it you?`;
    } else {
        wasItYou.style.display = 'none';
    }
}

async function bountyKillClaim(claimed) {
    const wasItYou = document.getElementById('bounty-was-it-you');
    wasItYou.style.display = 'none';

    try {
        const resp = await fetch(`/api/games/${gameCode}/ability/bounty-kill?session_token=${sessionToken}&claimed=${claimed}`, {
            method: 'POST'
        });
        const data = await resp.json();
        if (data.success) {
            bountyKills = data.bounty_kills;
            bountyTargetId = data.new_target_id;
            document.getElementById('bounty-target-name').textContent = data.new_target_name || 'No target';
            updateBountyKillButton();
        } else {
            showError(data.detail || 'Failed');
        }
    } catch (e) {
        showError('Failed to process bounty');
    }
}

function showNoiseMakerSelect() {
    const modal = document.getElementById('noise-maker-modal');
    const list = document.getElementById('noise-maker-player-list');

    // Show alive players (excluding self)
    const alivePlayers = allPlayers.filter(p => p.status !== 'dead' && p.id !== playerId);

    list.innerHTML = alivePlayers.map(p => `
        <button class="btn btn-secondary" onclick="selectNoiseMakerTarget('${p.id}')" style="width: 100%; margin-bottom: 6px; font-size: 14px;">
            ${p.name}
        </button>
    `).join('');

    modal.style.display = 'flex';
}

async function selectNoiseMakerTarget(targetId) {
    const modal = document.getElementById('noise-maker-modal');
    const targetPlayer = allPlayers.find(p => p.id === targetId);
    const targetName = targetPlayer ? targetPlayer.name : 'this player';

    if (!confirm(`Select ${targetName}? They will "find" your body and a meeting will be called.`)) return;

    // Disable all buttons in the modal
    modal.querySelectorAll('button').forEach(btn => btn.disabled = true);

    try {
        const resp = await fetch(`/api/games/${gameCode}/ability/noise-maker-select?session_token=${sessionToken}&target_player_id=${targetId}`, {
            method: 'POST'
        });
        if (resp.ok) {
            modal.style.display = 'none';
            // Meeting will be triggered via WebSocket broadcast
        } else {
            const data = await resp.json();
            showError(data.detail || 'Failed to select target');
            modal.querySelectorAll('button').forEach(btn => btn.disabled = false);
        }
    } catch (e) {
        showError('Failed to select target');
        modal.querySelectorAll('button').forEach(btn => btn.disabled = false);
    }
}

function updateVultureBodyList() {
    const list = document.getElementById('vulture-body-list');
    if (!list) return;

    // Filter out bodies we've already eaten AND bodies discovered in meetings/voted out
    const deadPlayers = allPlayers.filter(p => p.status === 'dead' && p.id !== playerId && !vultureEatenBodyIds.includes(p.id) && !vultureIneligibleBodyIds.includes(p.id));
    if (deadPlayers.length === 0) {
        list.innerHTML = '<p style="color: var(--text-secondary); text-align: center; font-size: 13px;">No bodies to eat</p>';
        return;
    }

    list.innerHTML = deadPlayers.map(p => `
        <button class="vulture-eat-btn" onclick="vultureEat('${p.id}', '${p.name}')">
            EAT ${p.name.toUpperCase()}
        </button>
    `).join('');
}

async function vultureEat(targetId, targetName) {
    if (!confirm(`Eat ${targetName}'s body? Tell them to act alive until the next meeting.`)) return;

    try {
        const response = await fetch(`/api/games/${gameCode}/ability/vulture-eat?session_token=${sessionToken}&body_player_id=${targetId}`, {
            method: 'POST'
        });
        if (response.ok) {
            const data = await response.json();
            document.getElementById('vulture-count').textContent = data.bodies_eaten || 0;
            // Track eaten body locally so it disappears from the list
            if (!vultureEatenBodyIds.includes(targetId)) {
                vultureEatenBodyIds.push(targetId);
            }
            updateVultureBodyList();
            if (data.vulture_wins) {
                showError('You ate enough bodies! Vulture wins!');
            }
        } else {
            const data = await response.json();
            showError(data.detail || 'Failed to eat body');
        }
    } catch (e) {
        showError('Failed to eat body');
    }
}

// ==================== LOOKOUT ====================

function openLookoutSelect() {
    const modal = document.getElementById('lookout-modal');
    const list = document.getElementById('lookout-player-list');

    // Use lookoutSelectablePlayers from game state (populated in updateRoleUI)
    const players = lookoutSelectablePlayers.length > 0
        ? lookoutSelectablePlayers
        : allPlayers.filter(p => p.status !== 'dead' && p.id !== playerId);

    list.innerHTML = players.map(p => `
        <button class="btn btn-secondary" onclick="selectLookoutTarget('${p.id}', '${p.name}')" style="width: 100%; margin-bottom: 6px; font-size: 14px;">
            ${p.name}
        </button>
    `).join('');

    if (players.length === 0) {
        list.innerHTML = '<p style="color: #94a3b8; text-align: center;">No players to watch</p>';
    }

    modal.style.display = 'flex';
}

function closeLookoutModal() {
    document.getElementById('lookout-modal').style.display = 'none';
}

async function selectLookoutTarget(targetId, targetName) {
    closeLookoutModal();
    try {
        const resp = await fetch(`/api/games/${gameCode}/ability/lookout-select?session_token=${sessionToken}&target_player_id=${targetId}`, {
            method: 'POST'
        });
        if (resp.ok) {
            document.getElementById('lookout-target-name').textContent = targetName;
        } else {
            const data = await resp.json();
            showError(data.detail || 'Failed to select target');
        }
    } catch (e) {
        showError('Failed to select target');
    }
}

function dismissLookoutAlert() {
    document.getElementById('lookout-alert-overlay').style.display = 'none';
}

function showCooldownTimer() {
    const timerSection = document.getElementById('cooldown-timer');

    // Show timer for Impostor, Rampager, Sheriff, or Lone Wolf
    if (KILL_COOLDOWN_ROLES.includes(myRole)) {
        timerSection.style.display = 'block';
    } else {
        timerSection.style.display = 'none';
    }
}

function getCooldownForRole() {
    // Return role-specific cooldown
    if (myRole === 'Impostor') {
        return settings.impostor_kill_cooldown || settings.kill_cooldown || 30;
    } else if (myRole === 'Rampager') {
        // Base impostor cooldown minus 5s per bounty kill, minimum 10s
        const base = settings.impostor_kill_cooldown || settings.kill_cooldown || 30;
        return Math.max(10, base - (5 * bountyKills));
    } else if (myRole === 'Sheriff') {
        return settings.sheriff_shoot_cooldown || settings.kill_cooldown || 30;
    } else if (myRole === 'Lone Wolf') {
        return settings.lone_wolf_kill_cooldown || settings.kill_cooldown || 30;
    }
    return settings.kill_cooldown || 30;
}

function startCooldown() {
    const cooldownSeconds = getCooldownForRole();
    cooldownEndTime = Date.now() + (cooldownSeconds * 1000);

    document.getElementById('start-cooldown-btn').style.display = 'none';
    updateCooldownDisplay();

    if (killCooldownTimer) clearInterval(killCooldownTimer);
    killCooldownTimer = setInterval(updateCooldownDisplay, 100);
}

function updateCooldownDisplay() {
    const cooldownText = document.getElementById('cooldown-text');
    const startBtn = document.getElementById('start-cooldown-btn');

    if (!cooldownEndTime) {
        cooldownText.textContent = 'Kill Ready';
        cooldownText.classList.add('ready');
        startBtn.style.display = 'inline-block';
        return;
    }

    const remaining = cooldownEndTime - Date.now();

    if (remaining <= 0) {
        // Cooldown finished
        cooldownEndTime = null;
        clearInterval(killCooldownTimer);
        killCooldownTimer = null;

        cooldownText.textContent = 'KILL READY!';
        cooldownText.classList.add('ready');
        startBtn.style.display = 'inline-block';

        // Vibrate to notify (if enabled)
        if (settings.vibrate_cooldown && navigator.vibrate) {
            navigator.vibrate([100, 50, 100, 50, 100]);
        }
    } else {
        // Still on cooldown
        const seconds = Math.ceil(remaining / 1000);
        cooldownText.textContent = `Kill Cooldown: ${seconds}s`;
        cooldownText.classList.remove('ready');
    }
}
