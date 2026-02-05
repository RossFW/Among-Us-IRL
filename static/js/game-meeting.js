// game-meeting.js - Meeting flow, voting, guesser modal, swapper UI

function resetMeetingState() {
    meetingState = {
        phase: null,
        callerId: null,
        callerName: null,
        meetingType: null,
        hasVoted: false,
        warningPlayed: false,
        votingEnabled: false,
        payload: null,
        discussionEndsAt: null,
        votingEndsAt: null
    };
    // Clear all meeting-related timers
    if (meetingTimerInterval) {
        clearInterval(meetingTimerInterval);
        meetingTimerInterval = null;
    }
    if (discussionTimerInterval) {
        clearInterval(discussionTimerInterval);
        discussionTimerInterval = null;
    }
    if (voteResultsTimerInterval) {
        clearInterval(voteResultsTimerInterval);
        voteResultsTimerInterval = null;
    }
}

function renderMeetingPhase() {
    // Central function to render UI based on meeting phase
    const gathering = document.getElementById('gathering-section');
    const voting = document.getElementById('voting-section');
    const results = document.getElementById('vote-results-section');
    const timer = document.getElementById('meeting-timer');
    const endBtn = document.getElementById('end-meeting-btn');
    const playersSection = document.getElementById('meeting-players-section');

    // Hide all meeting sections first
    gathering.style.display = 'none';
    voting.style.display = 'none';
    results.style.display = 'none';
    timer.style.display = 'none';
    endBtn.style.display = 'none';
    playersSection.style.display = 'none';

    if (!meetingState.votingEnabled) {
        // Voting disabled - just show player lists
        playersSection.style.display = 'block';
        return;
    }

    switch (meetingState.phase) {
        case 'gathering':
            gathering.style.display = 'block';
            // Show START MEETING only for caller
            const isCaller = playerId === meetingState.callerId;
            const startBtn = document.getElementById('start-meeting-btn');
            if (isCaller) {
                startBtn.style.display = 'block';
                startBtn.textContent = 'START MEETING';
                // Disable briefly to prevent ghost clicks from screen transition
                startBtn.disabled = true;
                setTimeout(() => {
                    startBtn.disabled = false;
                }, 1200);
            } else {
                startBtn.style.display = 'none';
            }
            document.getElementById('gathering-message').style.display = isCaller ? 'none' : 'block';
            break;

        case 'voting':
            voting.style.display = 'block';
            timer.style.display = 'block';
            // END MEETING hidden during voting - only show after results
            break;

        case 'results':
            results.style.display = 'block';
            // END MEETING button hidden initially - shown after vote_results_duration countdown
            // (handleVoteResults starts the countdown)
            break;
    }
}

function restoreMeetingState(activeMeeting) {
    // Restore meeting state after reconnection
    resetMeetingState();

    meetingState.phase = activeMeeting.phase;
    meetingState.callerId = activeMeeting.caller_id;
    meetingState.callerName = activeMeeting.caller_name;
    meetingState.meetingType = activeMeeting.meeting_type;
    meetingState.hasVoted = activeMeeting.has_voted;
    meetingState.votingEnabled = true;  // If we're in meeting, voting is enabled
    meetingState.payload = {
        alive_players: activeMeeting.alive_players,
        dead_players: activeMeeting.dead_players
    };

    // Setup meeting header
    const meetingHeader = document.getElementById('meeting-header');
    const meetingTitle = document.getElementById('meeting-title');
    const meetingCaller = document.getElementById('meeting-caller');

    if (activeMeeting.meeting_type === 'body_report') {
        meetingHeader.classList.add('body-report');
        meetingTitle.textContent = 'DEAD BODY REPORTED';
    } else {
        meetingHeader.classList.remove('body-report');
        meetingTitle.textContent = 'EMERGENCY MEETING';
    }

    // Show caller name if past gathering phase
    if (activeMeeting.phase !== 'gathering') {
        meetingCaller.textContent = activeMeeting.meeting_type === 'body_report'
            ? `Reported by ${activeMeeting.caller_name}`
            : `Called by ${activeMeeting.caller_name}`;
    } else {
        meetingCaller.textContent = '';
    }

    // Populate player lists
    document.getElementById('alive-list').innerHTML = activeMeeting.alive_players.map(p => `
        <div class="player-item">${p.name}</div>
    `).join('');

    document.getElementById('dead-list').innerHTML = activeMeeting.dead_players.map(p => `
        <div class="player-item dead">${p.name}</div>
    `).join('');

    // Reset vote feed
    const voteFeed = document.getElementById('vote-feed');
    voteFeed.innerHTML = '';
    voteFeed.style.display = 'none';

    // Setup phase-specific UI
    if (activeMeeting.phase === 'voting') {
        // Restore voting UI
        const votingSection = document.getElementById('voting-section');
        const voteOptions = document.getElementById('vote-options');
        const skipBtn = document.getElementById('skip-vote-btn');

        const me = allPlayers.find(p => p.id === playerId);
        const amAlive = me && me.status !== 'dead';
        const inDeadList = activeMeeting.dead_players.some(p => p.id === playerId);
        const canVote = amAlive && !inDeadList;

        if (canVote && !activeMeeting.has_voted) {
            voteOptions.innerHTML = activeMeeting.alive_players
                .map(p => `
                    <button class="btn vote-btn" onclick="castVote('${p.id}')">
                        ${p.name}
                    </button>
                `).join('');
            skipBtn.style.display = 'block';
            skipBtn.disabled = false;
        } else if (activeMeeting.has_voted) {
            voteOptions.innerHTML = '<div class="dead-voter-message">You have already voted.</div>';
            skipBtn.style.display = 'none';
        } else {
            voteOptions.innerHTML = '<div class="dead-voter-message">You are dead. You cannot vote.</div>';
            skipBtn.style.display = 'none';
        }

        // Update vote counts
        document.getElementById('votes-cast-count').textContent = activeMeeting.votes_cast;
        document.getElementById('votes-needed-count').textContent = activeMeeting.votes_needed;

        // Start timer from remaining time
        if (activeMeeting.voting_remaining > 0) {
            meetingEndTime = Date.now() + (activeMeeting.voting_remaining * 1000);
            startMeetingTimer(activeMeeting.voting_remaining, settings.meeting_warning_time || 30);
        }
    } else if (activeMeeting.phase === 'results' && activeMeeting.result) {
        // Show results
        const resultsList = document.getElementById('vote-results-list');
        let resultsHtml = '';

        const sortedResults = Object.entries(activeMeeting.result.vote_counts || {})
            .sort((a, b) => b[1] - a[1]);

        for (const [name, count] of sortedResults) {
            const isEliminated = activeMeeting.result.eliminated_name === name;
            resultsHtml += `
                <div class="vote-result-item ${isEliminated ? 'eliminated' : ''}">
                    <span class="vote-result-name">${name}</span>
                    <span class="vote-result-count">${count} vote${count !== 1 ? 's' : ''}</span>
                </div>
            `;
        }

        if (activeMeeting.result.skip_count > 0) {
            resultsHtml += `
                <div class="vote-result-item skip">
                    <span class="vote-result-name">Skip</span>
                    <span class="vote-result-count">${activeMeeting.result.skip_count} vote${activeMeeting.result.skip_count !== 1 ? 's' : ''}</span>
                </div>
            `;
        }

        resultsList.innerHTML = resultsHtml;

        // Show outcome
        const outcomeEl = document.getElementById('vote-outcome');
        if (activeMeeting.result.outcome === 'eliminated') {
            outcomeEl.innerHTML = `<span class="eliminated-name">${activeMeeting.result.eliminated_name}</span> was ejected.`;
        } else if (activeMeeting.result.outcome === 'tie') {
            outcomeEl.textContent = 'Tie vote - no one was ejected.';
        } else {
            outcomeEl.textContent = 'No one was ejected.';
        }
        // On reconnect during results, show END MEETING immediately for everyone
        const endBtn = document.getElementById('end-meeting-btn');
        const countdownEl = document.getElementById('vote-results-countdown');
        endBtn.style.display = 'block';
        if (countdownEl) countdownEl.textContent = '';
    }

    // Render phase UI
    renderMeetingPhase();
    showScreen('meeting-screen');
}

// ==================== MEETING COOLDOWN ====================

function startMeetingCooldown() {
    meetingCooldownEnd = Date.now() + (settings.meeting_cooldown * 1000);
    updateMeetingButtonCooldown();

    if (meetingCooldownInterval) clearInterval(meetingCooldownInterval);
    meetingCooldownInterval = setInterval(() => {
        updateMeetingButtonCooldown();
        if (Date.now() >= meetingCooldownEnd) {
            clearInterval(meetingCooldownInterval);
            meetingCooldownInterval = null;
        }
    }, 1000);
}

function updateMeetingButtonCooldown() {
    const btn = document.getElementById('call-meeting-btn');
    if (!btn) return;

    // If already used meeting, keep it disabled with "MEETING USED" text
    if (hasUsedMeeting) {
        btn.textContent = 'MEETING USED';
        btn.disabled = true;
        return;
    }

    if (meetingCooldownEnd && Date.now() < meetingCooldownEnd) {
        const remaining = Math.ceil((meetingCooldownEnd - Date.now()) / 1000);
        btn.textContent = `MEETING (${remaining}s)`;
        btn.disabled = true;
    } else {
        btn.textContent = 'CALL MEETING';
        btn.disabled = activeSabotage !== null;  // Still disabled during sabotage
    }

    // Also update captain button cooldown if it exists
    updateCaptainButtonCooldown();
}

function updateCaptainButtonCooldown() {
    const btn = document.getElementById('captain-meeting-btn');
    if (!btn || btn.style.display === 'none') return;

    // If already used, keep showing "REMOTE MEETING USED"
    if (btn.textContent === 'REMOTE MEETING USED') return;

    if (meetingCooldownEnd && Date.now() < meetingCooldownEnd) {
        const remaining = Math.ceil((meetingCooldownEnd - Date.now()) / 1000);
        btn.textContent = `REMOTE MEETING (${remaining}s)`;
        btn.disabled = true;
    } else {
        btn.textContent = 'REMOTE MEETING';
        btn.disabled = activeSabotage !== null;
    }
}

// ==================== CALL MEETING / REPORT BODY ====================

async function callMeeting() {
    const btn = document.getElementById('call-meeting-btn');

    // Can only call meeting once per game
    if (hasUsedMeeting) {
        return;
    }

    // Check meeting cooldown
    if (meetingCooldownEnd && Date.now() < meetingCooldownEnd) {
        return;  // Still on cooldown
    }

    // Check if sabotage is active (can't call meeting during sabotage)
    if (activeSabotage) {
        showError('Cannot call meeting during sabotage!');
        return;
    }

    btn.disabled = true;

    try {
        const response = await fetch(`/api/games/${gameCode}/meeting/start?session_token=${sessionToken}`, {
            method: 'POST'
        });
        if (response.ok) {
            // Mark meeting as used - can't use again this game
            hasUsedMeeting = true;
            btn.textContent = 'MEETING USED';
            btn.disabled = true;
        }
    } catch (e) {
        showError('Failed to call meeting');
        btn.disabled = false;
    }
}

async function reportBody() {
    // Report body always works - no cooldown constraint
    const btn = document.getElementById('report-body-btn');
    btn.disabled = true;

    try {
        await fetch(`/api/games/${gameCode}/meeting/start?session_token=${sessionToken}&meeting_type=body_report`, {
            method: 'POST'
        });
    } catch (e) {
        showError('Failed to report body');
    } finally {
        btn.disabled = false;
    }
}

// ==================== MEETING START & VOTING PHASE ====================

function handleMeetingStart(payload) {
    // ALWAYS reset meeting state first - clean slate!
    resetMeetingState();
    guesserDead = false;  // Reset guesser state for new meeting

    // Update consolidated meeting state
    meetingState.phase = 'gathering';
    meetingState.callerId = payload.caller_id;
    meetingState.callerName = payload.called_by;
    meetingState.meetingType = payload.meeting_type;
    meetingState.votingEnabled = payload.enable_voting || false;
    meetingState.payload = payload;

    // Setup meeting header
    const meetingHeader = document.getElementById('meeting-header');
    const meetingTitle = document.getElementById('meeting-title');
    const meetingCaller = document.getElementById('meeting-caller');

    // Display differently for body report vs emergency meeting
    // HIDE reporter identity until meeting officially starts
    if (payload.meeting_type === 'body_report') {
        meetingHeader.classList.add('body-report');
        meetingTitle.textContent = 'DEAD BODY REPORTED';
        meetingCaller.textContent = '';  // Hidden until meeting starts
    } else {
        meetingHeader.classList.remove('body-report');
        meetingTitle.textContent = 'EMERGENCY MEETING';
        meetingCaller.textContent = '';  // Hidden until meeting starts
    }

    updateProgress(payload.task_percentage);

    // Mark all currently dead bodies as ineligible for vulture (discovered in meeting)
    if (myRole === 'Vulture') {
        payload.dead_players.forEach(p => {
            if (!vultureIneligibleBodyIds.includes(p.id)) {
                vultureIneligibleBodyIds.push(p.id);
            }
        });
    }

    // Populate player lists
    document.getElementById('alive-list').innerHTML = payload.alive_players.map(p => `
        <div class="player-item">${p.name}</div>
    `).join('');

    document.getElementById('dead-list').innerHTML = payload.dead_players.map(p => `
        <div class="player-item dead">${p.name}</div>
    `).join('');

    // Reset vote feed
    const voteFeed = document.getElementById('vote-feed');
    voteFeed.innerHTML = '';
    voteFeed.style.display = 'none';

    // Close Noise Maker selection modal if open (edge case: another player reports body first)
    const noiseMakerModal = document.getElementById('noise-maker-modal');
    if (noiseMakerModal) {
        noiseMakerModal.style.display = 'none';
    }

    // Hide lights sabotage banner during meeting (will re-show on meeting end if still active)
    if (activeSabotage && activeSabotage.type === 'lights') {
        document.getElementById('sabotage-alert').style.display = 'none';
    }

    // Render UI based on phase
    renderMeetingPhase();

    showScreen('meeting-screen');

    // Play meeting sound
    playSound('sound-meeting');

    // Vibrate (if enabled)
    if (settings.vibrate_meeting && navigator.vibrate) navigator.vibrate([200, 100, 200]);
}

async function startVotingPhase() {
    // Called when the meeting caller clicks START MEETING
    const btn = document.getElementById('start-meeting-btn');
    btn.disabled = true;
    btn.textContent = 'Starting...';

    try {
        const response = await fetch(`/api/games/${gameCode}/meeting/start_voting?session_token=${sessionToken}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const data = await response.json();
            showError(data.detail || 'Failed to start meeting');
            btn.disabled = false;
            btn.textContent = 'START MEETING';
        }
        // Success - WebSocket will broadcast voting_started to everyone
    } catch (e) {
        showError('Failed to start meeting');
        btn.disabled = false;
        btn.textContent = 'START MEETING';
    }
}

function handleVotingStarted(payload) {
    // Update meeting state
    meetingState.phase = 'voting';
    meetingState.hasVoted = false;

    // Store timestamps for reference
    const now = Date.now();
    const discussionTime = payload.discussion_time || 0;
    const timerDuration = payload.timer_duration || 120;
    meetingState.discussionEndsAt = now + (discussionTime * 1000);
    meetingState.votingEndsAt = now + (timerDuration * 1000);

    // Render phase UI (hides gathering, shows voting)
    renderMeetingPhase();

    // NOW reveal who called the meeting
    const meetingCaller = document.getElementById('meeting-caller');
    if (meetingState.meetingType === 'body_report') {
        meetingCaller.textContent = `Reported by ${meetingState.callerName}`;
    } else {
        meetingCaller.textContent = `Called by ${meetingState.callerName}`;
    }

    // Check if current player is alive (only alive players can vote)
    const me = allPlayers.find(p => p.id === playerId);
    const amAlive = me && me.status !== 'dead';
    // Also check if we're in the dead list
    const inDeadList = meetingState.payload && meetingState.payload.dead_players.some(p => p.id === playerId);
    const canVote = amAlive && !inDeadList;

    // Setup voting UI
    const votingSection = document.getElementById('voting-section');
    const voteOptions = document.getElementById('vote-options');
    const skipBtn = document.getElementById('skip-vote-btn');

    const isGuesser = GUESSER_ROLES.includes(myRole);

    // Check if any guesser role is enabled in game settings
    const roleConfigs = settings.role_configs || {};
    const hasGuessersInGame = (roleConfigs.nice_guesser && roleConfigs.nice_guesser.enabled) ||
                              (roleConfigs.evil_guesser && roleConfigs.evil_guesser.enabled);

    if (canVote) {
        // Populate vote options with alive players (including self - Jester strategy!)
        voteOptions.innerHTML = payload.alive_players
            .map(p => `
                <div class="vote-btn-wrapper" style="display: flex; gap: 4px; margin-bottom: 4px;">
                    <button class="btn vote-btn" onclick="castVote('${p.id}')" ${discussionTime > 0 ? 'disabled' : ''} style="flex: 1;">
                        ${p.name}
                    </button>
                    ${hasGuessersInGame && p.id !== playerId ? `<button class="btn guesser-guess-btn" onclick="handleGuessButton('${p.id}', '${p.name}')" ${discussionTime > 0 ? 'disabled' : ''} style="width: 36px; min-width: 36px; padding: 0; font-size: 16px; background: #14b8a6;">?</button>` : ''}
                </div>
            `).join('');

        // Setup skip button
        skipBtn.style.display = 'block';
        skipBtn.disabled = discussionTime > 0;
        skipBtn.classList.remove('voted');
    } else {
        // Dead players see a message instead of voting options
        voteOptions.innerHTML = '<div class="dead-voter-message">You are dead. You cannot vote.</div>';
        skipBtn.style.display = 'none';
    }

    // Update vote counts
    document.getElementById('votes-cast-count').textContent = '0';
    document.getElementById('votes-needed-count').textContent = payload.alive_players.length;

    // Handle discussion time countdown
    if (discussionTime > 0) {
        // Show discussion countdown in the voting section header
        const votingHeader = votingSection.querySelector('h3');
        let remaining = discussionTime;
        votingHeader.textContent = `Discussion Time: ${remaining}s`;
        votingHeader.classList.add('discussion-countdown');

        discussionTimerInterval = setInterval(() => {
            remaining--;
            if (remaining > 0) {
                votingHeader.textContent = `Discussion Time: ${remaining}s`;
            } else {
                // Discussion time ended - enable voting!
                clearInterval(discussionTimerInterval);
                discussionTimerInterval = null;
                votingHeader.textContent = 'Vote to Eliminate';
                votingHeader.classList.remove('discussion-countdown');

                // Play "time to vote" sound when voting begins
                playSound('sound-time-to-vote');

                // Enable all vote buttons (including guesser buttons)
                if (canVote) {
                    voteOptions.querySelectorAll('.vote-btn, .guesser-guess-btn').forEach(btn => btn.disabled = false);
                    skipBtn.disabled = false;
                }
            }
        }, 1000);

        // Start the full meeting timer (includes discussion time)
        startMeetingTimer(timerDuration, payload.warning_time || 30);
    } else {
        // No discussion time - play sound and enable voting immediately
        playSound('sound-time-to-vote');

        // Start meeting timer
        startMeetingTimer(timerDuration, payload.warning_time || 30);
    }

    // Show Swapper UI if player is Swapper and alive
    const swapperSection = document.getElementById('swapper-section');
    if (myRole === 'Swapper' && canVote) {
        swapperSection.style.display = 'block';
        swapPlayer1 = null;
        swapPlayer2 = null;
        swapConfirmed = false;
        document.getElementById('swap-player1-btn').textContent = '[Select Player 1]';
        document.getElementById('swap-player2-btn').textContent = '[Select Player 2]';
        document.getElementById('confirm-swap-btn').disabled = true;
        document.getElementById('swapper-controls').style.display = 'block';
        document.getElementById('swapper-result').style.display = 'none';
        swapAlivePlayers = payload.alive_players;
    } else {
        swapperSection.style.display = 'none';
    }
}

// ==================== VOTING FUNCTIONS ====================

function startMeetingTimer(durationSeconds, warningTime) {
    if (meetingTimerInterval) clearInterval(meetingTimerInterval);

    meetingEndTime = Date.now() + (durationSeconds * 1000);
    meetingState.warningPlayed = false;

    updateMeetingTimerDisplay();
    meetingTimerInterval = setInterval(() => {
        updateMeetingTimerDisplay();

        const remaining = Math.max(0, meetingEndTime - Date.now());
        const remainingSeconds = Math.ceil(remaining / 1000);

        // Play warning sound
        if (!meetingState.warningPlayed && remainingSeconds <= warningTime && remainingSeconds > 0) {
            meetingState.warningPlayed = true;
            playSound('sound-voting-warning');
            if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
        }

        // Timer expired
        if (remaining <= 0) {
            clearInterval(meetingTimerInterval);
            meetingTimerInterval = null;
            handleTimerExpired();
        }
    }, 100);
}

function updateMeetingTimerDisplay() {
    const display = document.getElementById('meeting-timer-display');
    if (!meetingEndTime) {
        display.textContent = '0:00';
        return;
    }

    const remaining = Math.max(0, meetingEndTime - Date.now());
    const totalSeconds = Math.ceil(remaining / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;

    display.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;

    // Add warning class when low
    const timerCircle = document.querySelector('.timer-circle');
    if (timerCircle) {
        if (totalSeconds <= 30) {
            timerCircle.classList.add('warning');
        } else {
            timerCircle.classList.remove('warning');
        }
        if (totalSeconds <= 10) {
            timerCircle.classList.add('critical');
        } else {
            timerCircle.classList.remove('critical');
        }
    }
}

async function handleTimerExpired() {
    // Notify server that timer expired
    try {
        await fetch(`/api/games/${gameCode}/meeting/timer_expired?session_token=${sessionToken}`, {
            method: 'POST'
        });
    } catch (e) {
        console.error('Failed to notify timer expired:', e);
    }
}

async function castVote(targetId) {
    if (meetingState.hasVoted) return;

    // Disable all vote buttons immediately
    const allVoteBtns = document.querySelectorAll('.vote-btn, #skip-vote-btn');
    allVoteBtns.forEach(btn => btn.disabled = true);

    try {
        const url = targetId
            ? `/api/games/${gameCode}/vote?session_token=${sessionToken}&target_id=${targetId}`
            : `/api/games/${gameCode}/vote?session_token=${sessionToken}`;

        const response = await fetch(url, { method: 'POST' });

        if (response.ok) {
            meetingState.hasVoted = true;
            // Highlight the selected vote
            if (targetId) {
                const votedBtn = document.querySelector(`.vote-btn[onclick="castVote('${targetId}')"]`);
                if (votedBtn) votedBtn.classList.add('voted');
            } else {
                document.getElementById('skip-vote-btn').classList.add('voted');
            }
        } else {
            // Re-enable buttons on error
            allVoteBtns.forEach(btn => btn.disabled = false);
            const data = await response.json();
            showError(data.detail || 'Failed to cast vote');
        }
    } catch (e) {
        // Re-enable buttons on error
        allVoteBtns.forEach(btn => btn.disabled = false);
        showError('Connection error');
    }
}

function handleVoteCast(payload) {
    // Update vote count display only - individual votes shown at results
    document.getElementById('votes-cast-count').textContent = payload.votes_cast;
    document.getElementById('votes-needed-count').textContent = payload.votes_needed;
}

function handleVoteResults(payload) {
    // Update meeting state to results phase
    meetingState.phase = 'results';

    // Stop the timer
    if (meetingTimerInterval) {
        clearInterval(meetingTimerInterval);
        meetingTimerInterval = null;
    }
    if (discussionTimerInterval) {
        clearInterval(discussionTimerInterval);
        discussionTimerInterval = null;
    }

    // Play "time to vote" sound (voting ended)
    playSound('sound-time-to-vote');

    // Render results phase UI
    renderMeetingPhase();

    // Debug: log the payload to see what we're getting
    console.log('Vote results payload:', payload);

    // Display vote counts with voters listed under each name
    const resultsList = document.getElementById('vote-results-list');
    let resultsHtml = '';

    // Sort by vote count descending
    const sortedResults = Object.entries(payload.vote_counts)
        .sort((a, b) => b[1] - a[1]);

    // Get votes_by_target for showing who voted for whom
    const votesByTarget = payload.votes_by_target || {};

    const swappedNames = payload.swapped_names || [];

    for (const [name, count] of sortedResults) {
        const isEliminated = payload.eliminated_name === name;
        const isSwapped = swappedNames.includes(name);
        const voters = votesByTarget[name] || [];
        const votersText = voters.length > 0 ? `(${voters.join(', ')})` : '';

        resultsHtml += `
            <div class="vote-result-item ${isEliminated ? 'eliminated' : ''}">
                <div class="vote-result-main">
                    <span class="vote-result-name">${name}${isSwapped ? ' <span style="color: #ec4899; font-size: 12px;">(Swapped)</span>' : ''}</span>
                    <span class="vote-result-count">${count} vote${count !== 1 ? 's' : ''}</span>
                </div>
                ${votersText ? `<div class="vote-result-voters">${votersText}</div>` : ''}
            </div>
        `;
    }

    // Show skip votes
    if (payload.skip_count > 0) {
        const skipVoters = votesByTarget['Skip'] || [];
        const skipVotersText = skipVoters.length > 0 ? `(${skipVoters.join(', ')})` : '';

        resultsHtml += `
            <div class="vote-result-item skip">
                <div class="vote-result-main">
                    <span class="vote-result-name">Skip</span>
                    <span class="vote-result-count">${payload.skip_count} vote${payload.skip_count !== 1 ? 's' : ''}</span>
                </div>
                ${skipVotersText ? `<div class="vote-result-voters">${skipVotersText}</div>` : ''}
            </div>
        `;
    }

    resultsList.innerHTML = resultsHtml;

    // Display outcome
    const outcomeEl = document.getElementById('vote-outcome');
    if (payload.eliminated_name) {
        outcomeEl.textContent = `${payload.eliminated_name} was ejected.`;
        outcomeEl.className = 'vote-outcome ejected';
    } else if (payload.outcome === 'tie') {
        outcomeEl.textContent = 'No one was ejected. (Tie)';
        outcomeEl.className = 'vote-outcome no-eject';
    } else {
        outcomeEl.textContent = 'No one was ejected. (Skipped)';
        outcomeEl.className = 'vote-outcome no-eject';
    }

    // Hide the old vote feed (we now show voters inline)
    const voteFeed = document.getElementById('vote-feed');
    voteFeed.style.display = 'none';

    // Start vote results countdown before showing END MEETING button
    const duration = settings.vote_results_duration || 10;
    let remaining = duration;
    const countdownEl = document.getElementById('vote-results-countdown');
    const endBtn = document.getElementById('end-meeting-btn');
    endBtn.style.display = 'none';
    countdownEl.textContent = `Returning in ${remaining}s...`;

    if (voteResultsTimerInterval) clearInterval(voteResultsTimerInterval);
    voteResultsTimerInterval = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
            clearInterval(voteResultsTimerInterval);
            voteResultsTimerInterval = null;
            countdownEl.textContent = '';
            // Show END MEETING button for everyone
            endBtn.style.display = 'block';
        } else {
            countdownEl.textContent = `Returning in ${remaining}s...`;
        }
    }, 1000);
}

async function endMeeting() {
    try {
        await fetch(`/api/games/${gameCode}/meeting/end?session_token=${sessionToken}`, {
            method: 'POST'
        });
    } catch (e) {
        showError('Failed to end meeting');
    }
}

function handleMeetingEnd() {
    // CLEAN SLATE: Reset all meeting state
    resetMeetingState();

    showScreen('game-screen');

    // Ensure dead players' buttons stay disabled after meeting
    const me = allPlayers.find(p => p.id === playerId);
    if (me && me.status === 'dead') {
        document.getElementById('im-dead-btn').disabled = true;
        document.getElementById('im-dead-btn').textContent = 'YOU ARE DEAD';
        const meetBtn = document.getElementById('call-meeting-btn');
        meetBtn.disabled = true;
        meetBtn.textContent = 'YOU ARE DEAD';
        meetBtn.className = 'btn btn-secondary';
        document.getElementById('report-body-btn').disabled = true;
    }

    // Reset kill cooldown timer after meeting for impostor/bounty hunter/sheriff/lone wolf
    if (KILL_COOLDOWN_ROLES.includes(myRole)) {
        startCooldown();
    }

    // Start meeting cooldown for everyone
    startMeetingCooldown();

    // Re-show lights sabotage alert if still active (lights persists through meetings)
    if (activeSabotage && activeSabotage.type === 'lights') {
        document.getElementById('sabotage-alert').style.display = 'block';
        playSound('sound-lights-sabotage');  // Remind players lights are still off
        // Disable call meeting during sabotage (if not already used)
        if (!hasUsedMeeting) {
            document.getElementById('call-meeting-btn').disabled = true;
        }
    }

    // Reset sabotage cooldown after meeting for impostor-aligned roles
    if (IMPOSTOR_SABOTAGE_ROLES.includes(myRole) && settings.enable_sabotage) {
        sabotageCooldownEnd = Date.now() + (settings.sabotage_cooldown * 1000);
        startSabotageCooldownTimer();
        updateImpostorSabotageButtons();
    }

    // Update vulture body list (ineligible bodies removed after meeting)
    if (myRole === 'Vulture') {
        updateVultureBodyList();
    }
}

// ==================== SWAPPER ====================

function openSwapSelect(slot) {
    if (swapConfirmed) return;
    swapSelectSlot = slot;
    const modal = document.getElementById('swap-select-modal');
    const options = document.getElementById('swap-select-options');
    options.innerHTML = swapAlivePlayers.map(p => `
        <button class="btn btn-secondary" onclick="selectSwapPlayer('${p.id}', '${p.name}')" style="width: 100%; margin-bottom: 4px; font-size: 13px;">${p.name}</button>
    `).join('');
    modal.style.display = 'flex';
}

function closeSwapSelect() {
    document.getElementById('swap-select-modal').style.display = 'none';
}

function selectSwapPlayer(id, name) {
    if (swapSelectSlot === 1) {
        swapPlayer1 = { id, name };
        document.getElementById('swap-player1-btn').textContent = name;
    } else {
        swapPlayer2 = { id, name };
        document.getElementById('swap-player2-btn').textContent = name;
    }
    closeSwapSelect();

    // Enable confirm button if both selected
    document.getElementById('confirm-swap-btn').disabled = !(swapPlayer1 && swapPlayer2);
}

async function confirmSwap() {
    if (!swapPlayer1 || !swapPlayer2 || swapConfirmed) return;

    swapConfirmed = true;
    document.getElementById('confirm-swap-btn').disabled = true;

    try {
        const resp = await fetch(`/api/games/${gameCode}/ability/swapper-swap?session_token=${sessionToken}&player1_id=${swapPlayer1.id}&player2_id=${swapPlayer2.id}`, {
            method: 'POST'
        });
        const data = await resp.json();
        if (resp.ok) {
            document.getElementById('swapper-controls').style.display = 'none';
            document.getElementById('swapper-result').style.display = 'block';
            document.getElementById('swapper-result').textContent = `Swap set: ${swapPlayer1.name} ↔ ${swapPlayer2.name}`;
        } else {
            showError(data.detail || 'Swap failed');
            swapConfirmed = false;
            document.getElementById('confirm-swap-btn').disabled = false;
        }
    } catch (e) {
        showError('Failed to set swap');
        swapConfirmed = false;
        document.getElementById('confirm-swap-btn').disabled = false;
    }
}

// ==================== GUESSER ====================

function handleGuessButton(targetId, targetName) {
    const isGuesser = GUESSER_ROLES.includes(myRole);
    if (isGuesser) {
        openGuesserModal(targetId, targetName);
    }
    // Non-guessers: do nothing (button is just for disguise)
}

function openGuesserModal(targetId, targetName) {
    if (guesserDead) return;
    guesserTargetId = targetId;
    guesserTargetName = targetName;

    document.getElementById('guesser-target-label').textContent = `Guessing ${targetName}'s role:`;

    // Build role options from cached role guide or from all known roles
    const allRoles = [
        { name: 'Crewmate', color: '#4ade80' },
        { name: 'Sheriff', color: '#3b82f6' },
        { name: 'Engineer', color: '#22c55e' },
        { name: 'Captain', color: '#0ea5e9' },
        { name: 'Mayor', color: '#8b5cf6' },
        { name: 'Bounty Hunter', color: '#14b8a6' },
        { name: 'Spy', color: '#6366f1' },
        { name: 'Swapper', color: '#ec4899' },
        { name: 'Impostor', color: '#ef4444' },
        { name: 'Riddler', color: '#dc2626' },
        { name: 'Rampager', color: '#b91c1c' },
        { name: 'Cleaner', color: '#991b1b' },
        { name: 'Venter', color: '#7c2d12' },
        { name: 'Minion', color: '#eab308' },
        { name: 'Jester', color: '#a855f7' },
        { name: 'Lone Wolf', color: '#f97316' },
        { name: 'Vulture', color: '#84cc16' },
        { name: 'Noise Maker', color: '#f59e0b' }
    ];

    // Crew guesser (Bounty Hunter): only show generic "Impostor" option
    // Impostor guesser (Riddler): show all roles (can guess anyone as anything)
    let displayRoles;
    if (myRole === 'Bounty Hunter') {
        displayRoles = allRoles.filter(r => !IMPOSTOR_SUBTYPES.includes(r.name));
    } else {
        displayRoles = allRoles;
    }

    const options = document.getElementById('guesser-role-options');
    options.innerHTML = displayRoles.map(r => `
        <button class="btn" onclick="confirmGuesserGuess('${r.name}')" style="width: 100%; margin-bottom: 4px; font-size: 13px; background: rgba(255,255,255,0.05); border: 1px solid ${r.color}; color: ${r.color};">
            ${r.name}
        </button>
    `).join('');

    document.getElementById('guesser-modal').style.display = 'flex';
}

function closeGuesserModal() {
    document.getElementById('guesser-modal').style.display = 'none';
    guesserTargetId = null;
    guesserTargetName = null;
}

async function confirmGuesserGuess(roleName) {
    if (!guesserTargetId || guesserDead) return;

    if (!confirm(`Guess ${guesserTargetName} is ${roleName}?\n\nWrong guess = YOU DIE!`)) return;

    closeGuesserModal();

    try {
        const resp = await fetch(`/api/games/${gameCode}/ability/guesser-guess?session_token=${sessionToken}&target_id=${guesserTargetId}&guessed_role=${encodeURIComponent(roleName)}`, {
            method: 'POST'
        });
        // Result handled via WebSocket broadcast (guesser_result)
        if (!resp.ok) {
            const data = await resp.json();
            showError(data.detail || 'Guess failed');
        }
    } catch (e) {
        showError('Failed to submit guess');
    }
}

function handleGuesserResult(payload) {
    // Play death during meeting sound
    playSound('sound-death-meeting');

    // If the dead player is ME, show death overlay and disable voting
    if (payload.dead_player_id === playerId) {
        guesserDead = true;
        // Disable all vote buttons and guesser buttons
        document.querySelectorAll('.vote-btn, .guesser-guess-btn, #skip-vote-btn').forEach(btn => {
            btn.disabled = true;
        });
        meetingState.hasVoted = true;
        // Show death overlay
        showMeetingDeathOverlay(payload);
    } else {
        // Show toast to everyone else
        showError(payload.message);
    }

    // Strike through dead player's name for ALL voters (regardless of correct/wrong guess)
    if (payload.dead_player_id) {
        const wrappers = document.querySelectorAll('.vote-btn-wrapper');
        wrappers.forEach(w => {
            const voteBtn = w.querySelector('.vote-btn');
            if (voteBtn && voteBtn.textContent.trim() === payload.dead_player_name) {
                voteBtn.disabled = true;
                voteBtn.style.textDecoration = 'line-through';
                voteBtn.style.opacity = '0.5';
                const guessBtn = w.querySelector('.guesser-guess-btn');
                if (guessBtn) {
                    guessBtn.disabled = true;
                    guessBtn.style.opacity = '0.5';
                }
            }
        });
    }

    // Update vote count (server scrubs dead player's vote)
    if (payload.votes_cast !== undefined) {
        document.getElementById('votes-cast-count').textContent = payload.votes_cast;
    }
    if (payload.votes_needed !== undefined) {
        document.getElementById('votes-needed-count').textContent = payload.votes_needed;
    }

    // Update allPlayers
    const deadP = allPlayers.find(p => p.id === payload.dead_player_id);
    if (deadP) deadP.status = 'dead';
}

function showMeetingDeathOverlay(payload) {
    // Remove existing overlay if any
    const existing = document.getElementById('meeting-death-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'meeting-death-overlay';
    overlay.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); z-index: 3000; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;';

    const msg = payload.correct
        ? 'You were identified and eliminated!'
        : 'Your guess was wrong. You are dead!';

    overlay.innerHTML = `
        <div style="color: #ef4444; font-size: 32px; font-weight: bold; text-transform: uppercase; text-shadow: 0 0 20px rgba(239,68,68,0.5);">YOU ARE DEAD</div>
        <div style="color: #94a3b8; font-size: 16px; max-width: 280px; text-align: center;">${msg}</div>
        <button onclick="this.parentElement.remove()" class="btn" style="margin-top: 16px; background: #6b7280; padding: 10px 32px; font-size: 16px;">DISMISS</button>
    `;
    document.body.appendChild(overlay);
}
