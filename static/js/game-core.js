// game-core.js - State management, WebSocket, settings, game lifecycle

// === State Variables (shared globals used by all game-*.js files) ===
let ws = null;
let gameState = 'lobby';
let isHost = false;
let myRole = null;
let hasUsedMeeting = false;  // Track if player used their one emergency meeting
let settings = { tasks_per_player: 5, num_impostors: 2, enable_jester: false, enable_lone_wolf: false, enable_minion: false, enable_sheriff: false, kill_cooldown: 45, impostor_kill_cooldown: 45, sheriff_shoot_cooldown: 45, lone_wolf_kill_cooldown: 45, enable_sabotage: false, sabotage_cooldown: 90, meeting_cooldown: 30, enable_voting: true, anonymous_voting: false, meeting_timer_duration: 120, meeting_warning_time: 30, discussion_time: 5, vote_results_duration: 10, role_configs: {} };
let killCooldownTimer = null;
let cooldownEndTime = null;
let bountyKills = 0;
let bountyTargetId = null;
let availableTasks = [];
let allPlayers = [];

// Meeting state - consolidated into single object for clean state management
let meetingState = {
    phase: null,           // null, 'gathering', 'voting', 'results'
    callerId: null,
    callerName: null,
    meetingType: null,     // 'meeting' or 'body_report'
    hasVoted: false,
    warningPlayed: false,
    votingEnabled: false,
    payload: null,         // Full payload for reference
    discussionEndsAt: null,
    votingEndsAt: null
};

// Timer intervals (kept separate for easy cleanup)
let meetingTimerInterval = null;
let discussionTimerInterval = null;
let voteResultsTimerInterval = null;

// Legacy compatibility
let meetingEndTime = null;

// Meeting cooldown
let meetingCooldownEnd = null;
let meetingCooldownInterval = null;

// Sabotage state
let activeSabotage = null;
let sabotageTimerInterval = null;
let sabotageCooldownEnd = null;
let sabotageCooldownInterval = null;

// Swapper state
let swapPlayer1 = null;
let swapPlayer2 = null;
let swapConfirmed = false;
let swapAlivePlayers = [];
let swapSelectSlot = 0;  // Which slot we're selecting for (1 or 2)

// Guesser state
let guesserTargetId = null;
let guesserTargetName = null;
let guesserDead = false;

// Vulture state
let vultureEatenBodyIds = [];  // Track which bodies we've already eaten
let vultureIneligibleBodyIds = [];  // Bodies discovered in meetings or voted out

// Map gallery
let currentMapIndex = 0;

// Role guide
let roleGuideCache = null;

// === Session Redirect ===
if (!sessionToken) {
    window.location.href = '/';
}

// === Sound Helper ===
function playSound(soundId) {
    const sound = document.getElementById(soundId);
    if (sound) {
        sound.currentTime = 0;
        sound.play().catch(e => console.log('Sound play failed:', e));
    }
}

// === WebSocket ===
function connectWS() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/${gameCode}/${sessionToken}`);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onclose = () => {
        console.log('WebSocket closed, reconnecting...');
        setTimeout(connectWS, 2000);
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

function handleMessage(msg) {
    console.log('Received:', msg);

    switch (msg.type) {
        case 'state_sync':
            handleStateSync(msg.payload);
            break;
        case 'player_joined':
        case 'player_connected':
        case 'player_disconnected':
        case 'player_left':
            refreshGame();
            break;
        case 'settings_changed':
            settings = msg.payload;
            updateSettingsUI();
            break;
        case 'tasks_updated':
            availableTasks = msg.payload.tasks;
            updateTasksUI();
            break;
        case 'game_started':
            handleGameStart(msg.payload);
            break;
        case 'task_completed':
            // Don't update progress bar in real-time - only visible during meetings
            break;
        case 'meeting_called':
            handleMeetingStart(msg.payload);
            break;
        case 'meeting_ended':
            handleMeetingEnd();
            break;
        case 'player_died':
            handlePlayerDeath(msg.payload);
            break;
        case 'game_ended':
            handleGameEnd(msg.payload);
            break;
        case 'sabotage_started':
            handleSabotageStarted(msg.payload);
            break;
        case 'sabotage_resolved':
            handleSabotageResolved(msg.payload);
            break;
        case 'sabotage_update':
            handleSabotageUpdate(msg.payload);
            break;
        case 'voting_started':
            handleVotingStarted(msg.payload);
            break;
        case 'vote_cast':
            handleVoteCast(msg.payload);
            break;
        case 'vote_results':
            handleVoteResults(msg.payload);
            break;
        case 'body_eaten':
            // Dead player notification that vulture ate their body
            if (msg.payload && msg.payload.message) {
                showError(msg.payload.message);
            }
            break;
        case 'guesser_result':
            handleGuesserResult(msg.payload);
            break;
        case 'bounty_target_update':
            if (myRole === 'Rampager' && msg.payload) {
                bountyTargetId = msg.payload.target_id;
                bountyKills = msg.payload.bounty_kills || bountyKills;
                document.getElementById('bounty-target-name').textContent = msg.payload.target_name || 'No target';
                updateBountyKillButton();
            }
            break;
    }
}

function handleStateSync(payload) {
    allPlayers = payload.players;
    updatePlayers(payload.players);
    updateProgress(payload.task_percentage);

    if (payload.role_info) {
        myRole = payload.role_info.role;
        updateRoleUI(payload.role_info);
    }

    if (payload.game_state === 'playing') {
        showScreen('game-screen');

        // Show sabotage UI for impostor-aligned roles
        if (IMPOSTOR_SABOTAGE_ROLES.includes(myRole) && settings.enable_sabotage) {
            showImpostorSabotageUI();
        }

        // Restore active sabotage state on reconnect
        if (payload.active_sabotage) {
            handleSabotageStarted(payload.active_sabotage);
            // Update fix progress for reactor/o2
            if (payload.active_sabotage.type === 'reactor') {
                document.getElementById('sabotage-fix-info').textContent =
                    `${payload.active_sabotage.reactor_holders}/2 people holding`;
            } else if (payload.active_sabotage.type === 'o2') {
                document.getElementById('sabotage-fix-info').textContent =
                    `${payload.active_sabotage.o2_switches}/2 switches`;
            }
        }
    } else if (payload.game_state === 'meeting') {
        // Restore meeting state on reconnect
        if (payload.active_meeting) {
            restoreMeetingState(payload.active_meeting);
        } else {
            showScreen('meeting-screen');
        }
    } else if (payload.game_state === 'ended') {
        showScreen('gameover-screen');
    }
}

// === Player & Settings UI ===

function updatePlayers(players) {
    const list = document.getElementById('player-list');
    const count = document.getElementById('player-count');

    list.innerHTML = players.map(p => `
        <div class="player-item ${p.connected ? '' : 'disconnected'} ${p.is_host ? 'host' : ''}">
            <span class="player-name">${p.name}${p.is_host ? ' (Host)' : ''}</span>
            <span class="status-dot ${p.connected ? 'online' : 'offline'}"></span>
        </div>
    `).join('');

    count.textContent = `(${players.length})`;

    // Check if current player is host
    const me = players.find(p => p.id === playerId);
    if (me) {
        isHost = me.is_host;
        document.getElementById('host-controls').style.display = isHost ? 'block' : 'none';
        document.getElementById('waiting-message').style.display = isHost ? 'none' : 'block';
    }
}

function updateSettingsUI() {
    document.getElementById('setting-tasks').textContent = settings.tasks_per_player;
    document.getElementById('setting-impostors').textContent = settings.num_impostors;
    // Per-character cooldowns
    document.getElementById('setting-impostor-cooldown').textContent = settings.impostor_kill_cooldown || settings.kill_cooldown;
    document.getElementById('setting-sheriff-cooldown').textContent = settings.sheriff_shoot_cooldown || settings.kill_cooldown;
    document.getElementById('setting-lonewolf-cooldown').textContent = settings.lone_wolf_kill_cooldown || settings.kill_cooldown;
    updateCooldownSettingsVisibility();
    updateSabotageSettingsUI();
    updateMeetingSettingsUI();
    updateAdvancedRolesUI();
}

function updateCooldownSettingsVisibility() {
    const cooldownSection = document.getElementById('cooldown-settings');
    const sheriffRow = document.getElementById('sheriff-cooldown-row');
    const lonewolfRow = document.getElementById('lonewolf-cooldown-row');

    // Always show cooldown settings (impostor always has one)
    cooldownSection.style.display = 'block';

    // Show Sheriff cooldown row only if Sheriff is enabled
    sheriffRow.style.display = settings.enable_sheriff ? 'flex' : 'none';

    // Show Lone Wolf cooldown row only if Lone Wolf is enabled
    lonewolfRow.style.display = settings.enable_lone_wolf ? 'flex' : 'none';
}

async function adjustSetting(type, delta) {
    let update = {};
    if (type === 'tasks') {
        const newVal = Math.max(1, Math.min(10, settings.tasks_per_player + delta));
        update.tasks_per_player = newVal;
    } else if (type === 'impostors') {
        const newVal = Math.max(1, Math.min(3, settings.num_impostors + delta));
        update.num_impostors = newVal;
    } else if (type === 'cooldown') {
        const newVal = Math.max(10, Math.min(120, settings.kill_cooldown + delta));
        update.kill_cooldown = newVal;
    } else if (type === 'impostor_cooldown') {
        const current = settings.impostor_kill_cooldown || settings.kill_cooldown;
        const newVal = Math.max(10, Math.min(120, current + delta));
        update.impostor_kill_cooldown = newVal;
    } else if (type === 'sheriff_cooldown') {
        const current = settings.sheriff_shoot_cooldown || settings.kill_cooldown;
        const newVal = Math.max(10, Math.min(120, current + delta));
        update.sheriff_shoot_cooldown = newVal;
    } else if (type === 'lonewolf_cooldown') {
        const current = settings.lone_wolf_kill_cooldown || settings.kill_cooldown;
        const newVal = Math.max(10, Math.min(120, current + delta));
        update.lone_wolf_kill_cooldown = newVal;
    } else if (type === 'sabotage_cooldown') {
        const current = settings.sabotage_cooldown || 90;
        const newVal = Math.max(10, Math.min(180, current + delta));
        update.sabotage_cooldown = newVal;
    } else if (type === 'meeting_timer') {
        const current = settings.meeting_timer_duration || 120;
        const newVal = Math.max(30, Math.min(300, current + delta));
        update.meeting_timer_duration = newVal;
    } else if (type === 'meeting_warning') {
        const current = settings.meeting_warning_time || 30;
        const maxWarning = settings.meeting_timer_duration || 120;
        const newVal = Math.max(0, Math.min(maxWarning, current + delta));
        update.meeting_warning_time = newVal;
    } else if (type === 'discussion_time') {
        const current = settings.discussion_time || 5;
        const newVal = Math.max(0, Math.min(60, current + delta));  // 0-60 seconds
        update.discussion_time = newVal;
    } else if (type === 'vote_results_duration') {
        const current = settings.vote_results_duration || 10;
        const newVal = Math.max(5, Math.min(30, current + delta));
        update.vote_results_duration = newVal;
    } else if (type === 'vulture_eat_count') {
        const current = settings.vulture_eat_count || 3;
        const newVal = Math.max(1, Math.min(10, current + delta));
        update.vulture_eat_count = newVal;
    }

    await fetch(`/api/games/${gameCode}/settings?session_token=${sessionToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update)
    });
}

// === Settings Toggle Functions ===

function toggleSabotageSettings() {
    const content = document.getElementById('sabotage-settings-content');
    const icon = document.getElementById('sabotage-toggle-icon');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '-';
    } else {
        content.style.display = 'none';
        icon.textContent = '+';
    }
}

function toggleAdvancedRoles() {
    const content = document.getElementById('advanced-roles-content');
    const icon = document.getElementById('advanced-roles-toggle-icon');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '-';
    } else {
        content.style.display = 'none';
        icon.textContent = '+';
    }
}

async function toggleAdvancedRole(roleKey) {
    const checkbox = document.getElementById(`role-${roleKey}`);
    const enabled = checkbox.checked;

    // Show/hide vulture eat count sub-setting
    if (roleKey === 'vulture') {
        const vultureSetting = document.getElementById('vulture-eat-setting');
        if (vultureSetting) vultureSetting.style.display = enabled ? 'flex' : 'none';
    }

    await fetch(`/api/games/${gameCode}/settings?session_token=${sessionToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            role_configs: {
                [roleKey]: { enabled: enabled }
            }
        })
    });
}

function updateAdvancedRolesUI() {
    const roleConfigs = settings.role_configs || {};
    const advancedRoles = ['engineer', 'captain', 'mayor', 'nice_guesser', 'spy', 'swapper',
                          'evil_guesser', 'bounty_hunter', 'cleaner', 'venter', 'vulture', 'noise_maker'];

    for (const roleKey of advancedRoles) {
        const checkbox = document.getElementById(`role-${roleKey}`);
        if (checkbox) {
            const config = roleConfigs[roleKey] || { enabled: false };
            checkbox.checked = config.enabled;
        }
    }

    // Update legacy roles that are now in advanced section
    document.getElementById('toggle-jester').checked = settings.enable_jester;
    document.getElementById('toggle-lonewolf').checked = settings.enable_lone_wolf;
    document.getElementById('toggle-minion').checked = settings.enable_minion;
    document.getElementById('toggle-sheriff').checked = settings.enable_sheriff;

    // Show/hide vulture eat count sub-setting
    const vultureConfig = roleConfigs['vulture'] || { enabled: false };
    const vultureSetting = document.getElementById('vulture-eat-setting');
    if (vultureSetting) {
        vultureSetting.style.display = vultureConfig.enabled ? 'flex' : 'none';
    }
    const vultureCountDisplay = document.getElementById('vulture-eat-count-display');
    if (vultureCountDisplay) {
        vultureCountDisplay.textContent = settings.vulture_eat_count || 3;
    }
}

async function toggleSabotageSetting() {
    const enabled = document.getElementById('toggle-sabotage').checked;
    document.getElementById('sabotage-config').style.display = enabled ? 'block' : 'none';

    await fetch(`/api/games/${gameCode}/settings?session_token=${sessionToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enable_sabotage: enabled })
    });
}

async function toggleSabotageItem(index) {
    const enabled = document.getElementById(`toggle-sab-${index}`).checked;
    const update = {};
    update[`sabotage_${index}_enabled`] = enabled;

    await fetch(`/api/games/${gameCode}/settings?session_token=${sessionToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update)
    });
}

async function adjustSabotageTimer(index, delta) {
    const current = parseInt(document.getElementById(`sab-${index}-timer`).textContent) || 45;
    const newVal = Math.max(10, Math.min(120, current + delta));
    const update = {};
    update[`sabotage_${index}_timer`] = newVal;

    await fetch(`/api/games/${gameCode}/settings?session_token=${sessionToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update)
    });
}

function updateSabotageSettingsUI() {
    document.getElementById('toggle-sabotage').checked = settings.enable_sabotage;
    document.getElementById('sabotage-config').style.display = settings.enable_sabotage ? 'block' : 'none';
    document.getElementById('setting-sabotage-cooldown').textContent = settings.sabotage_cooldown || 90;

    for (let i = 1; i <= 4; i++) {
        const enabled = settings[`sabotage_${i}_enabled`];
        const name = settings[`sabotage_${i}_name`];
        const timer = settings[`sabotage_${i}_timer`];

        const toggleEl = document.getElementById(`toggle-sab-${i}`);
        const nameEl = document.getElementById(`sab-${i}-name`);
        const timerEl = document.getElementById(`sab-${i}-timer`);

        if (toggleEl) toggleEl.checked = enabled;
        if (nameEl) nameEl.textContent = name;
        if (timerEl) timerEl.textContent = timer;
    }
}

// ==================== MEETING & VOTING SETTINGS ====================

function toggleMeetingSettings() {
    const content = document.getElementById('meeting-settings-content');
    const icon = document.getElementById('meeting-toggle-icon');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '-';
    } else {
        content.style.display = 'none';
        icon.textContent = '+';
    }
}

async function toggleVotingSetting() {
    const enabled = document.getElementById('toggle-voting').checked;

    // Update local settings immediately (optimistic update)
    settings.enable_voting = enabled;
    document.getElementById('voting-config').style.display = enabled ? 'block' : 'none';

    await fetch(`/api/games/${gameCode}/settings?session_token=${sessionToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enable_voting: enabled })
    });
}

async function toggleAnonymousVoting() {
    const anonymous = document.getElementById('toggle-anonymous').checked;

    // Update local settings immediately (optimistic update)
    settings.anonymous_voting = anonymous;

    await fetch(`/api/games/${gameCode}/settings?session_token=${sessionToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anonymous_voting: anonymous })
    });
}

function updateMeetingSettingsUI() {
    const toggleVoting = document.getElementById('toggle-voting');
    const toggleAnonymous = document.getElementById('toggle-anonymous');
    const votingConfig = document.getElementById('voting-config');
    const timerDisplay = document.getElementById('setting-meeting-timer');
    const warningDisplay = document.getElementById('setting-meeting-warning');
    const discussionDisplay = document.getElementById('setting-discussion-time');

    if (toggleVoting) {
        toggleVoting.checked = settings.enable_voting || false;
    }
    if (toggleAnonymous) {
        toggleAnonymous.checked = settings.anonymous_voting || false;
    }
    if (votingConfig) {
        votingConfig.style.display = settings.enable_voting ? 'block' : 'none';
    }
    if (timerDisplay) {
        timerDisplay.textContent = settings.meeting_timer_duration || 120;
    }
    if (warningDisplay) {
        warningDisplay.textContent = settings.meeting_warning_time || 30;
    }
    if (discussionDisplay) {
        discussionDisplay.textContent = settings.discussion_time ?? 5;
    }
    const resultsTimerDisplay = document.getElementById('setting-vote-results-duration');
    if (resultsTimerDisplay) {
        resultsTimerDisplay.textContent = settings.vote_results_duration || 10;
    }
}

async function toggleRole(role) {
    let update = {};
    if (role === 'jester') update.enable_jester = document.getElementById('toggle-jester').checked;
    if (role === 'lonewolf') update.enable_lone_wolf = document.getElementById('toggle-lonewolf').checked;
    if (role === 'minion') update.enable_minion = document.getElementById('toggle-minion').checked;
    if (role === 'sheriff') update.enable_sheriff = document.getElementById('toggle-sheriff').checked;

    await fetch(`/api/games/${gameCode}/settings?session_token=${sessionToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update)
    });
}

async function startGame() {
    const btn = document.getElementById('start-game-btn');
    btn.disabled = true;
    btn.textContent = 'STARTING...';

    try {
        const response = await fetch(`/api/games/${gameCode}/start?session_token=${sessionToken}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const data = await response.json();
            showError(data.detail || 'Failed to start game');
        }
    } catch (e) {
        showError('Connection error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'START GAME';
    }
}

// === Game Lifecycle ===

function handleGameStart(payload) {
    myRole = payload.role;
    updateRoleUI(payload);
    updateProgress(payload.task_percentage);
    showScreen('game-screen');

    // Scroll to top so player must scroll down to see their role
    window.scrollTo(0, 0);

    showCooldownTimer();

    // Play scary horror theme on game start
    playSound('sound-game-start');

    // Start kill cooldown timer at game start for impostor/bounty hunter/sheriff/lone wolf
    if (KILL_COOLDOWN_ROLES.includes(myRole)) {
        startCooldown();
    }

    // Start meeting cooldown at game start
    startMeetingCooldown();

    // Show sabotage UI for impostor-aligned roles (alive or dead can use it)
    if (IMPOSTOR_SABOTAGE_ROLES.includes(myRole) && settings.enable_sabotage) {
        showImpostorSabotageUI();
        // Start sabotage cooldown timer display
        sabotageCooldownEnd = Date.now() + (settings.sabotage_cooldown * 1000);
        startSabotageCooldownTimer();
    }
}

function updateRoleUI(roleInfo) {
    const roleDisplay = document.getElementById('role-display');
    const roleName = document.getElementById('role-name');
    const roleDesc = document.getElementById('role-description');
    const roleTeam = document.getElementById('role-team');
    const taskList = document.getElementById('task-list');
    const fellowImpostors = document.getElementById('fellow-impostors');
    const roleBadge = document.getElementById('role-badge');
    const roleNameBadge = document.getElementById('role-name-badge');

    roleName.textContent = roleInfo.role.toUpperCase();
    roleDisplay.className = 'role-display role-' + roleInfo.role.toLowerCase().replace(' ', '-');

    // Update compact role badge at top
    roleNameBadge.textContent = roleInfo.role.toUpperCase();
    roleBadge.className = 'role-badge role-' + roleInfo.role.toLowerCase().replace(' ', '-');

    // Team categorization
    const teams = {
        // Crewmate team
        'Crewmate': 'CREWMATE',
        'Sheriff': 'CREWMATE',
        'Engineer': 'CREWMATE',
        'Captain': 'CREWMATE',
        'Mayor': 'CREWMATE',
        'Bounty Hunter': 'CREWMATE',
        'Spy': 'CREWMATE',
        'Swapper': 'CREWMATE',
        // Impostor team
        'Impostor': 'IMPOSTOR',
        'Riddler': 'IMPOSTOR',
        'Rampager': 'IMPOSTOR',
        'Cleaner': 'IMPOSTOR',
        'Venter': 'IMPOSTOR',
        'Minion': 'IMPOSTOR',
        // Neutral
        'Jester': 'NEUTRAL',
        'Lone Wolf': 'NEUTRAL',
        'Vulture': 'NEUTRAL',
        'Noise Maker': 'CREWMATE'
    };
    const team = teams[roleInfo.role] || 'CREWMATE';
    roleTeam.textContent = team;
    roleTeam.className = 'role-team team-' + team.toLowerCase();

    const descriptions = {
        // Crewmate team
        'Crewmate': 'Complete your tasks. Find the impostors.',
        'Sheriff': 'Complete tasks. Whisper to shoot someone - miss and you die!',
        'Engineer': 'You can fix ONE sabotage remotely per game.',
        'Captain': 'Call a remote meeting from anywhere (one use per game).',
        'Mayor': 'Your vote counts twice during meetings.',
        'Bounty Hunter': 'During voting, guess a player\'s role. Wrong guess = you die.',
        'Spy': 'You appear as an impostor to the impostor team.',
        'Swapper': 'Swap votes between two players. Cannot call emergency meetings.',
        // Impostor team
        'Impostor': 'Eliminate crewmates. Don\'t get caught.',
        'Riddler': 'Like impostor, but can guess roles during voting. Wrong = you die.',
        'Rampager': 'Shorter cooldown killing your target, longer for others.',
        'Cleaner': 'You can clean bodies - drag them elsewhere before they\'re found.',
        'Venter': 'You can "vent" - access doors and walk outside the building.',
        'Minion': 'Help the impostors eliminate crewmates. You don\'t know who they are. You cannot kill.',
        // Neutral
        'Jester': 'Get yourself voted out to win!',
        'Lone Wolf': 'Survive until you\'re the last one standing.',
        'Vulture': `Eat ${roleInfo.bodies_needed || 3} bodies to win. Touch body & tell dead player to act alive.`,
        'Noise Maker': 'When killed, select who "found" you (fake body report).'
    };
    roleDesc.textContent = descriptions[roleInfo.role] || '';

    // Show tasks (no fake label shown - would reveal role if someone peeks at phone)
    taskList.innerHTML = roleInfo.tasks.map(t => `
        <div class="task-item ${t.status === 'completed' ? 'completed' : ''}" data-id="${t.id}">
            <span class="task-check" onclick="toggleTask('${t.id}')">${t.status === 'completed' ? '\u2713' : ''}</span>
            <span class="task-name">${t.name}</span>
        </div>
    `).join('');

    // Show fellow impostors
    if (roleInfo.fellow_impostors && roleInfo.fellow_impostors.length > 0) {
        fellowImpostors.style.display = 'block';
        document.getElementById('impostor-names').textContent = roleInfo.fellow_impostors.map(i => i.name).join(', ');
    } else {
        fellowImpostors.style.display = 'none';
    }

    // Show Jester voted out button only for Jesters
    const jesterBtn = document.getElementById('jester-voted-btn');
    jesterBtn.style.display = roleInfo.role === 'Jester' ? 'block' : 'none';

    // Show Engineer fix button only for Engineers
    const engineerBtn = document.getElementById('engineer-fix-btn');
    if (roleInfo.role === 'Engineer') {
        engineerBtn.style.display = 'block';
        if (roleInfo.remote_fix_available === false) {
            engineerBtn.disabled = true;
            engineerBtn.textContent = 'FIX USED';
        } else if (!activeSabotage) {
            engineerBtn.disabled = true;
            engineerBtn.textContent = 'NO ACTIVE SABOTAGE';
        } else {
            engineerBtn.disabled = false;
            engineerBtn.textContent = 'FIX SABOTAGE REMOTELY';
        }
    } else {
        engineerBtn.style.display = 'none';
    }

    // Show Captain remote meeting button only for Captains
    const captainBtn = document.getElementById('captain-meeting-btn');
    if (roleInfo.role === 'Captain') {
        captainBtn.style.display = 'block';
        if (roleInfo.extra_meeting_available === false) {
            captainBtn.disabled = true;
            captainBtn.textContent = 'REMOTE MEETING USED';
        } else {
            captainBtn.disabled = false;
            captainBtn.textContent = 'REMOTE MEETING';
        }
    } else {
        captainBtn.style.display = 'none';
    }

    // Show Vulture eat section only for Vultures
    const vultureSection = document.getElementById('vulture-eat-section');
    if (roleInfo.role === 'Vulture') {
        vultureSection.style.display = 'block';
        document.getElementById('vulture-count').textContent = roleInfo.bodies_eaten || 0;
        document.getElementById('vulture-needed').textContent = roleInfo.bodies_needed || 3;
        vultureEatenBodyIds = roleInfo.eaten_body_ids || [];
        vultureIneligibleBodyIds = roleInfo.ineligible_body_ids || [];
        updateVultureBodyList();
    } else {
        vultureSection.style.display = 'none';
    }

    // Show Rampager section
    const bountySection = document.getElementById('bounty-hunter-section');
    if (roleInfo.role === 'Rampager') {
        bountySection.style.display = 'block';
        bountyKills = roleInfo.bounty_kills || 0;
        if (roleInfo.bounty_target) {
            document.getElementById('bounty-target-name').textContent = roleInfo.bounty_target.name;
            bountyTargetId = roleInfo.bounty_target.id;
        } else {
            document.getElementById('bounty-target-name').textContent = 'No target';
            bountyTargetId = null;
        }
        updateBountyKillButton();
    } else {
        bountySection.style.display = 'none';
    }
}

function updateProgress(percentage) {
    const fills = document.querySelectorAll('.progress-fill');
    const texts = document.querySelectorAll('.progress-text');

    fills.forEach(fill => fill.style.width = percentage + '%');
    texts.forEach(text => text.textContent = percentage + '% Tasks Complete');
}

// === Death & Game End ===

function handlePlayerDeath(payload) {
    // Update allPlayers with death status
    const deadPlayer = allPlayers.find(p => p.id === payload.player_id);
    if (deadPlayer) {
        deadPlayer.status = 'dead';
    }

    // If it's a sheriff shot, show the outcome message
    if (payload.cause === 'sheriff_shot' && payload.message) {
        showError(payload.message);  // Using error styling for visibility
    }

    // Check if the dead player is us
    if (payload.player_id === playerId) {
        document.getElementById('im-dead-btn').disabled = true;
        document.getElementById('im-dead-btn').textContent = 'YOU ARE DEAD';
        document.getElementById('call-meeting-btn').disabled = true;
        document.getElementById('report-body-btn').disabled = true;
    }

    // Update bounty kill button if we're bounty hunter and our target died
    if (myRole === 'Rampager') {
        updateBountyKillButton();
    }

    // Update vulture body list if we're a vulture
    if (myRole === 'Vulture') {
        // Voted-out players are ineligible for vulture eating
        if (payload.cause === 'voted_out' && !vultureIneligibleBodyIds.includes(payload.player_id)) {
            vultureIneligibleBodyIds.push(payload.player_id);
        }
        updateVultureBodyList();
    }

    refreshGame();
}

function handleGameEnd(payload) {
    // Clear any active sabotage UI/timer so it doesn't trigger after game ends
    activeSabotage = null;
    document.getElementById('sabotage-alert').style.display = 'none';
    if (sabotageTimerInterval) {
        clearInterval(sabotageTimerInterval);
        sabotageTimerInterval = null;
    }

    document.getElementById('winner-text').textContent = payload.winner.toUpperCase() + 'S WIN!';

    document.getElementById('roles-list').innerHTML = payload.roles.map(p => `
        <div class="role-reveal-item">
            <span class="player-name">${p.name}</span>
            <span class="player-role role-${p.role?.toLowerCase().replace(' ', '-')}">${p.role || 'Unknown'}</span>
        </div>
    `).join('');

    showScreen('gameover-screen');

    // Play appropriate win sound based on winner
    const winner = payload.winner.toLowerCase();
    if (winner === 'crewmate') {
        playSound('sound-crewmate-win');
    } else if (winner === 'impostor') {
        playSound('sound-impostor-win');
    } else if (winner === 'jester') {
        playSound('sound-jester-win');
    } else if (winner === 'lone wolf') {
        playSound('sound-lonewolf-win');
    } else if (winner === 'vulture') {
        playSound('sound-vulture-win');
    }

    // Vibrate
    if (navigator.vibrate) navigator.vibrate([500]);
}

function returnToLobby() {
    localStorage.removeItem('session_token');
    localStorage.removeItem('player_id');
    // Keep player_name in localStorage for next game
    window.location.href = '/';
}

async function leaveGame() {
    if (!confirm('Are you sure you want to leave this game?')) return;

    try {
        const response = await fetch(`/api/games/${gameCode}/leave?session_token=${sessionToken}`, {
            method: 'POST'
        });

        if (response.ok) {
            localStorage.removeItem('session_token');
            localStorage.removeItem('player_id');
            // Keep player_name for next game
            window.location.href = '/';
        } else {
            const data = await response.json();
            showError(data.detail || 'Failed to leave game');
        }
    } catch (e) {
        showError('Connection error');
    }
}

async function refreshGame() {
    try {
        const response = await fetch(`/api/games/${gameCode}?session_token=${sessionToken}`);
        const data = await response.json();

        allPlayers = data.players;
        updatePlayers(data.players);
        settings = data.settings;
        availableTasks = data.available_tasks || [];
        updateSettingsUI();
        updateTasksUI();
        updateProgress(data.task_percentage);
    } catch (e) {
        console.error('Failed to refresh game:', e);
    }
}

// === Task Management ===

function toggleTaskList() {
    const content = document.getElementById('task-management-content');
    const icon = document.getElementById('task-toggle-icon');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '-';
    } else {
        content.style.display = 'none';
        icon.textContent = '+';
    }
}

function updateTasksUI() {
    const list = document.getElementById('available-tasks-list');
    if (!list) return;

    list.innerHTML = availableTasks.map(task => `
        <div class="available-task-item">
            <span>${task}</span>
            <button class="btn-remove" onclick="removeTask('${task}')">&times;</button>
        </div>
    `).join('');
}

async function addTask() {
    const input = document.getElementById('new-task-input');
    const taskName = input.value.trim();
    if (!taskName) return;

    try {
        await fetch(`/api/games/${gameCode}/tasks?session_token=${sessionToken}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_name: taskName })
        });
        input.value = '';
    } catch (e) {
        showError('Failed to add task');
    }
}

async function removeTask(taskName) {
    try {
        await fetch(`/api/games/${gameCode}/tasks/${encodeURIComponent(taskName)}?session_token=${sessionToken}`, {
            method: 'DELETE'
        });
    } catch (e) {
        showError('Failed to remove task');
    }
}

// === Rules, Map Gallery, Role Guide ===

function showRules() {
    // Update which rules are visible based on settings
    document.getElementById('rule-jester').style.display = settings.enable_jester ? 'block' : 'none';
    document.getElementById('rule-lonewolf').style.display = settings.enable_lone_wolf ? 'block' : 'none';
    document.getElementById('rule-minion').style.display = settings.enable_minion ? 'block' : 'none';
    document.getElementById('rule-sheriff').style.display = settings.enable_sheriff ? 'block' : 'none';

    document.getElementById('rules-modal').style.display = 'flex';
}

function hideRules() {
    document.getElementById('rules-modal').style.display = 'none';
}

function showMapGallery() {
    document.getElementById('map-modal').style.display = 'flex';
    goToMapSlide(0);
}

function hideMapGallery() {
    document.getElementById('map-modal').style.display = 'none';
}

function goToMapSlide(index) {
    const slides = document.querySelectorAll('.map-slide');
    const indicators = document.querySelectorAll('.map-indicator');

    if (index < 0) index = slides.length - 1;
    if (index >= slides.length) index = 0;

    slides.forEach((s, i) => s.classList.toggle('active', i === index));
    indicators.forEach((ind, i) => ind.classList.toggle('active', i === index));
    currentMapIndex = index;
}

function nextMapSlide() {
    goToMapSlide(currentMapIndex + 1);
}

function prevMapSlide() {
    goToMapSlide(currentMapIndex - 1);
}

// ==================== ROLE GUIDE ====================

async function showRoleGuide() {
    document.getElementById('role-guide-modal').style.display = 'flex';

    if (roleGuideCache) {
        renderRoleGuide(roleGuideCache);
        return;
    }

    try {
        const resp = await fetch(`/api/games/${gameCode}/role-guide?session_token=${sessionToken}`);
        if (resp.ok) {
            roleGuideCache = await resp.json();
            renderRoleGuide(roleGuideCache);
        }
    } catch (e) {
        document.getElementById('role-guide-content').innerHTML = '<p style="color: #ef4444;">Failed to load roles</p>';
    }
}

function renderRoleGuide(guide) {
    const container = document.getElementById('role-guide-content');
    let html = '';

    const sections = [
        { key: 'crew', title: 'Crew', color: '#4ade80' },
        { key: 'impostor', title: 'Impostor', color: '#ef4444' },
        { key: 'neutral', title: 'Neutral', color: '#a855f7' }
    ];

    for (const section of sections) {
        const roles = guide[section.key];
        if (!roles || roles.length === 0) continue;

        html += `<div style="margin-bottom: 15px;">`;
        html += `<h3 style="color: ${section.color}; margin-bottom: 8px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">${section.title}</h3>`;

        for (const role of roles) {
            html += `
                <div class="role-guide-item" onclick="this.querySelector('.role-guide-desc').classList.toggle('expanded')" style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 10px; margin-bottom: 6px; cursor: pointer;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: ${role.color}; font-weight: bold;">${role.name}</span>
                        <span style="color: #94a3b8; font-size: 12px;">${role.short}</span>
                    </div>
                    <div class="role-guide-desc" style="color: #cbd5e1; font-size: 13px; margin-top: 0; max-height: 0; overflow: hidden; transition: max-height 0.2s, margin-top 0.2s;">
                        ${role.description}
                    </div>
                </div>
            `;
        }
        html += `</div>`;
    }

    container.innerHTML = html;
}

function hideRoleGuide() {
    document.getElementById('role-guide-modal').style.display = 'none';
}

// === Modal Close Handler ===
document.addEventListener('click', (e) => {
    const rulesModal = document.getElementById('rules-modal');
    const mapModal = document.getElementById('map-modal');
    const roleGuideModal = document.getElementById('role-guide-modal');
    if (e.target === rulesModal) {
        hideRules();
    }
    if (e.target === mapModal) {
        hideMapGallery();
    }
    if (e.target === roleGuideModal) {
        hideRoleGuide();
    }
});

// === Utilities ===

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.style.display = 'none');
    document.getElementById(screenId).style.display = 'block';
}

function showError(msg) {
    const el = document.getElementById('error-message');
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(() => el.style.display = 'none', 3000);
}

// === Initialize ===
connectWS();
refreshGame();

// === Keepalive Ping ===
setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
    }
}, 30000);
