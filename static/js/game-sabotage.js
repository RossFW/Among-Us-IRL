// game-sabotage.js - Sabotage system (start, resolve, timers, UI)

function startSabotageCooldownTimer() {
    if (sabotageCooldownInterval) clearInterval(sabotageCooldownInterval);

    updateImpostorSabotageButtons();

    sabotageCooldownInterval = setInterval(() => {
        updateImpostorSabotageButtons();
        if (!sabotageCooldownEnd || Date.now() >= sabotageCooldownEnd) {
            clearInterval(sabotageCooldownInterval);
            sabotageCooldownInterval = null;
        }
    }, 1000);
}

function showImpostorSabotageUI() {
    const section = document.getElementById('impostor-sabotage-section');
    if (!section) return;

    // Show for all impostor-aligned roles (except Minion) when sabotage is enabled
    if (IMPOSTOR_SABOTAGE_ROLES.includes(myRole) && settings.enable_sabotage) {
        section.style.display = 'block';
        updateImpostorSabotageButtons();
    } else {
        section.style.display = 'none';
    }
}

function updateImpostorSabotageButtons() {
    const buttonsDiv = document.getElementById('impostor-sabotage-buttons');
    if (!buttonsDiv) return;

    let html = '';
    for (let i = 1; i <= 4; i++) {
        const enabled = settings[`sabotage_${i}_enabled`];
        if (!enabled) continue;

        const name = settings[`sabotage_${i}_name`];
        const disabled = activeSabotage !== null || (sabotageCooldownEnd && Date.now() < sabotageCooldownEnd);

        html += `<button class="sabotage-btn ${disabled ? 'on-cooldown' : ''}"
                         onclick="startSabotage(${i})"
                         ${disabled ? 'disabled' : ''}>
                    ${name}
                </button>`;
    }

    buttonsDiv.innerHTML = html;

    // Update cooldown display
    const cooldownDiv = document.getElementById('impostor-sabotage-cooldown');
    if (sabotageCooldownEnd && Date.now() < sabotageCooldownEnd) {
        const remaining = Math.ceil((sabotageCooldownEnd - Date.now()) / 1000);
        cooldownDiv.style.display = 'block';
        document.getElementById('impostor-sabotage-cooldown-time').textContent = remaining;
    } else {
        cooldownDiv.style.display = 'none';
    }
}

async function startSabotage(index) {
    try {
        const response = await fetch(`/api/games/${gameCode}/sabotage/start?sabotage_index=${index}&session_token=${sessionToken}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const data = await response.json();
            showError(data.detail || 'Failed to start sabotage');
        }
    } catch (e) {
        showError('Connection error');
    }
}

function handleSabotageStarted(payload) {
    activeSabotage = payload;

    // Update Engineer button if applicable
    updateEngineerButton();

    // Show alert
    document.getElementById('sabotage-alert').style.display = 'block';
    document.getElementById('active-sabotage-name').textContent = payload.name.toUpperCase() + '!';

    // Show timer if applicable
    if (payload.timer > 0) {
        document.getElementById('active-sabotage-timer').style.display = 'block';
        document.getElementById('sabotage-remaining').textContent = payload.timer;
        startSabotageTimer(payload.timer);
    } else {
        document.getElementById('active-sabotage-timer').style.display = 'none';
    }

    // Show appropriate fix button
    if (payload.type === 'reactor') {
        document.getElementById('fix-sabotage-btn').style.display = 'none';
        document.getElementById('hold-sabotage-btn').style.display = 'inline-block';
        document.getElementById('sabotage-fix-info').textContent = '2 people must HOLD simultaneously';
    } else if (payload.type === 'o2') {
        document.getElementById('fix-sabotage-btn').style.display = 'inline-block';
        document.getElementById('hold-sabotage-btn').style.display = 'none';
        document.getElementById('sabotage-fix-info').textContent = '2 switches needed (0/2)';
    } else {
        document.getElementById('fix-sabotage-btn').style.display = 'inline-block';
        document.getElementById('hold-sabotage-btn').style.display = 'none';
        document.getElementById('sabotage-fix-info').textContent = '';
    }

    // Disable call meeting during sabotage (report body still works)
    if (!hasUsedMeeting) {
        document.getElementById('call-meeting-btn').disabled = true;
    }

    // Update impostor UI
    updateImpostorSabotageButtons();

    // Play sabotage sound based on type
    if (payload.type === 'lights') {
        playSound('sound-lights-sabotage');
    } else {
        // Reactor and O2 use the same alarm sound
        playSound('sound-reactor-sabotage');
    }

    // Vibrate
    if (navigator.vibrate) navigator.vibrate([100, 50, 100, 50, 100, 50, 100]);
}

function startSabotageTimer(seconds) {
    let remaining = seconds;

    if (sabotageTimerInterval) clearInterval(sabotageTimerInterval);

    sabotageTimerInterval = setInterval(async () => {
        remaining--;
        document.getElementById('sabotage-remaining').textContent = remaining;

        if (remaining <= 0) {
            clearInterval(sabotageTimerInterval);
            // Check timeout on server
            await fetch(`/api/games/${gameCode}/sabotage/check_timeout?session_token=${sessionToken}`, {
                method: 'POST'
            });
        }
    }, 1000);
}

function handleSabotageResolved(payload) {
    activeSabotage = null;

    // Update Engineer button if applicable
    updateEngineerButton();

    // Hide alert (except for lights which persists - but we still hide alert UI)
    document.getElementById('sabotage-alert').style.display = 'none';

    if (sabotageTimerInterval) {
        clearInterval(sabotageTimerInterval);
        sabotageTimerInterval = null;
    }

    // Re-enable meeting button (if not already used)
    if (!hasUsedMeeting) {
        document.getElementById('call-meeting-btn').disabled = false;
    }

    // Play fixed sound based on type
    if (payload.type === 'lights') {
        playSound('sound-lights-fixed');
    } else {
        // Reactor and O2 use the same fixed sound
        playSound('sound-reactor-fixed');
    }

    // Set cooldown and start timer for impostor UI
    sabotageCooldownEnd = Date.now() + (settings.sabotage_cooldown * 1000);

    // Start the cooldown timer to update UI (for impostor-aligned roles)
    if (IMPOSTOR_SABOTAGE_ROLES.includes(myRole)) {
        startSabotageCooldownTimer();
    }

    // Update impostor UI
    updateImpostorSabotageButtons();
}

function handleSabotageUpdate(payload) {
    if (payload.type === 'reactor') {
        document.getElementById('sabotage-fix-info').textContent = `${payload.holders}/2 people holding`;
    } else if (payload.type === 'o2') {
        document.getElementById('sabotage-fix-info').textContent = `${payload.switches}/2 switches`;
    }
}

async function fixSabotage() {
    try {
        await fetch(`/api/games/${gameCode}/sabotage/fix?session_token=${sessionToken}&action=tap`, {
            method: 'POST'
        });
    } catch (e) {
        showError('Failed to fix sabotage');
    }
}

async function holdReactorStart() {
    try {
        await fetch(`/api/games/${gameCode}/sabotage/fix?session_token=${sessionToken}&action=hold_start`, {
            method: 'POST'
        });
        document.getElementById('hold-sabotage-btn').textContent = 'HOLDING...';
        document.getElementById('hold-sabotage-btn').classList.add('holding');
    } catch (e) {
        showError('Failed to hold');
    }
}

async function holdReactorEnd() {
    try {
        await fetch(`/api/games/${gameCode}/sabotage/fix?session_token=${sessionToken}&action=hold_end`, {
            method: 'POST'
        });
        document.getElementById('hold-sabotage-btn').textContent = 'HOLD TO FIX';
        document.getElementById('hold-sabotage-btn').classList.remove('holding');
    } catch (e) {
        // Ignore
    }
}
