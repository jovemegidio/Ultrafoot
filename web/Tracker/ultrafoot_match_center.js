(function () {
    if (window.__ultrafootTrackerLoaded) return;
    window.__ultrafootTrackerLoaded = true;

    const DEFAULT_HOME = ["#0052cc", "#ffffff"];
    const DEFAULT_AWAY = ["#188038", "#ffffff"];
    const SPEED_OPTIONS = [0.5, 1, 2, 4, 8];
    const FORMATION_HOME = [
        [6, 50, "GK", 1], [18, 18, "RB", 2], [18, 38, "CB", 3], [18, 62, "CB", 4], [18, 82, "LB", 5],
        [36, 24, "CM", 6], [38, 50, "CDM", 7], [36, 76, "CM", 8], [58, 22, "RW", 9], [64, 50, "ST", 10], [58, 78, "LW", 11],
    ];
    const FORMATION_AWAY = [
        [94, 50, "GK", 1], [82, 18, "RB", 2], [82, 38, "CB", 3], [82, 62, "CB", 4], [82, 82, "LB", 5],
        [64, 24, "CM", 6], [62, 50, "CDM", 7], [64, 76, "CM", 8], [42, 22, "RW", 9], [36, 50, "ST", 10], [42, 78, "LW", 11],
    ];

    let trackerOverlayTimer = null;
    let trackerNewsTimer = null;

    function mapColors(teamName, fallback) {
        const nameMap = typeof TEAM_NAME_MAP !== "undefined" ? TEAM_NAME_MAP : {};
        const colorMap = typeof TEAM_COLORS !== "undefined" ? TEAM_COLORS : {};
        const shortName = nameMap[teamName] || teamName;
        const palette = colorMap[shortName] || fallback;
        return {
            shortName,
            primary: palette[0] || fallback[0],
            text: palette[1] || fallback[1],
        };
    }

    function badgeHtml(teamName, size) {
        if (typeof getEscudoSync === "function") return getEscudoSync(teamName, size || 28);
        return "";
    }

    function speedButtons() {
        return SPEED_OPTIONS.map((speed) => {
            const active = matchSpeed === speed ? "btn-primary" : "btn-outline";
            const label = (typeof SPEED_LABELS !== "undefined" && SPEED_LABELS[speed]) || `${speed}x`;
            return `<button class="btn btn-sm ${active}" onclick="setMatchSpeed(${speed})">${label}</button>`;
        }).join("");
    }

    function statPill(id, label, left, right, suffix) {
        return (
            `<div class="tracker-stat-pill">` +
                `<span class="label">${esc(label)}</span>` +
                `<div class="values">` +
                    `<span class="team-value" id="${id}-left">${left}${suffix || ""}</span>` +
                    `<span class="sep">x</span>` +
                    `<span class="team-value" id="${id}-right">${right}${suffix || ""}</span>` +
                `</div>` +
            `</div>`
        );
    }

    function updateTrackerStat(id, left, right, suffix) {
        const leftEl = document.getElementById(`${id}-left`);
        const rightEl = document.getElementById(`${id}-right`);
        if (!leftEl || !rightEl) return;
        const end = suffix || "";
        leftEl.textContent = `${left}${end}`;
        rightEl.textContent = `${right}${end}`;
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function buildPlayers(teamKey, formation, palette) {
        return formation.map((entry, index) => ({
            id: `${teamKey}-${index + 1}`,
            number: entry[3],
            role: entry[2],
            team: teamKey,
            baseX: entry[0],
            baseY: entry[1],
            x: entry[0],
            y: entry[1],
            targetX: entry[0],
            targetY: entry[1],
            palette,
            dom: null,
        }));
    }

    function ensureActors(state) {
        const pitch = document.getElementById("trackerPitch");
        if (!pitch || state.domReady) return;

        state.players.forEach((player) => {
            const wrapper = document.createElement("div");
            wrapper.className = `tracker-player-wrapper ${player.team}`;
            wrapper.innerHTML =
                `<div class="tracker-jersey" style="background:${player.palette.primary};color:${player.palette.text};">${player.number}</div>` +
                `<div class="tracker-player-meta">` +
                    `<span class="tracker-player-name">${player.team === "home" ? "Casa" : "Fora"} ${player.number}</span>` +
                    `<span class="tracker-player-role">${player.role}</span>` +
                `</div>`;
            pitch.appendChild(wrapper);
            player.dom = wrapper;
        });

        state.ballDom = document.getElementById("trackerBall");
        state.domReady = true;
    }

    function syncActors(state) {
        ensureActors(state);
        state.players.forEach((player) => {
            if (!player.dom) return;
            player.dom.style.left = `${player.x}%`;
            player.dom.style.top = `${player.y}%`;
            player.dom.classList.toggle("has-ball", state.ballOwner === player.id);
        });
        if (state.ballDom) {
            state.ballDom.style.left = `${state.ball.x}%`;
            state.ballDom.style.top = `${state.ball.y}%`;
            state.ballDom.classList.toggle("shooting", state.ball.shooting);
            state.ballDom.classList.toggle("passing", Boolean(state.ball.pass));
            state.ballDom.classList.toggle("dead-ball", Boolean(state.ball.deadBall));
        }
    }

    function renderMomentum(momentum) {
        const holder = document.getElementById("trackerMomentumBars");
        if (!holder) return;
        const points = (momentum || []).slice(-16);
        if (points.length === 0) {
            holder.innerHTML = '<div class="tracker-chip">Sem momentum registrado ainda</div>';
            return;
        }
        holder.innerHTML = points.map((point) => {
            const isHome = point.time === matchData.time_casa;
            const height = clamp((point.intensidade || 1) * 18, 10, 70);
            const color = isHome ? "var(--team-home)" : "var(--team-away)";
            const title = `${point.min || 0}' - ${point.time || ""}`;
            return `<div class="tracker-momentum-bar" title="${esc(title)}" style="height:${height}px;background:${color};"></div>`;
        }).join("");
    }

    function trackerMarkup(match, homePalette, awayPalette) {
        return (
            `<div class="tracker-match-shell" style="--team-home:${homePalette.primary};--team-away:${awayPalette.primary};">` +
                `<div class="tracker-live-news" id="trackerLiveNews"><span class="label">Ultrafeed</span><span class="value" id="trackerLiveNewsText">Preparando o dia de jogo</span></div>` +
                `<div class="tracker-overlay-card" id="trackerOverlay">` +
                    `<div class="tracker-overlay-backdrop"></div>` +
                    `<div class="tracker-overlay-banner">` +
                        `<div class="tracker-overlay-label" id="trackerOverlayLabel">Evento</div>` +
                        `<div class="tracker-overlay-main" id="trackerOverlayMain">Inicio</div>` +
                        `<div class="tracker-overlay-sub" id="trackerOverlaySub">A partida vai começar</div>` +
                    `</div>` +
                `</div>` +
                `<div class="broadcast-scoreboard">` +
                    `<div class="sb-team home">${badgeHtml(match.time_casa, 28)}<span class="sb-team-name">${esc(match.time_casa)}</span></div>` +
                    `<div class="sb-score-box"><div class="sb-score-num" id="liveScoreCasa">0</div><div class="sb-score-sep">x</div><div class="sb-score-num" id="liveScoreFora">0</div></div>` +
                    `<div class="sb-team away"><span class="sb-team-name">${esc(match.time_fora)}</span>${badgeHtml(match.time_fora, 28)}</div>` +
                `</div>` +
                `<div class="tracker-top-row">` +
                    `<div class="tracker-timer-card">` +
                        `<div class="tracker-match-clock">` +
                            `<div class="tracker-clock-pill"><span class="tracker-clock-dot"></span><span class="tracker-clock-value" id="liveMinute">00:00</span></div>` +
                            `<div class="tracker-clock-copy"><div class="tracker-clock-meta">Match Center</div><div class="tracker-live-event" id="liveEvent">Aquecimento final</div></div>` +
                        `</div>` +
                        `<div class="tracker-speed-row">${speedButtons()}</div>` +
                    `</div>` +
                    `<div class="tracker-context-card">` +
                        `<div class="tracker-context-item"><span class="label">Competição</span><span class="value">${esc(match.competicao || "Liga")}</span></div>` +
                        `<div class="tracker-context-item"><span class="label">Clima</span><span class="value">${esc(match.clima || "Padrão")}</span></div>` +
                        `<div class="tracker-context-item"><span class="label">Gramado</span><span class="value">${match.nivel_gramado || 80}/100</span></div>` +
                        `<div class="tracker-context-item"><span class="label">Público</span><span class="value">${Number(match.publico || 0).toLocaleString("pt-BR")}</span></div>` +
                    `</div>` +
                `</div>` +
                `<div class="tracker-stats-bar">` +
                    statPill("tracker-stat-posse", "Posse", match.posse_casa || 50, (100 - (match.posse_casa || 50)).toFixed(1), "%") +
                    statPill("tracker-stat-shots", "Finalizações", 0, 0, "") +
                    statPill("tracker-stat-on-target", "No alvo", 0, 0, "") +
                    statPill("tracker-stat-xg", "xG", 0, 0, "") +
                    statPill("tracker-stat-corners", "Escanteios", 0, 0, "") +
                    statPill("tracker-stat-fouls", "Faltas", 0, 0, "") +
                `</div>` +
                `<div class="tracker-sub-bar">` +
                    `<button class="sub-btn" id="btnSubstituir" onclick="abrirSubstituicao()">Substituir</button>` +
                    `<span class="tracker-sub-count" id="subCounter">5 restantes</span>` +
                    `<div class="tracker-sub-history" id="subHistory"><div class="tracker-chip">Sem alterações ainda</div></div>` +
                `</div>` +
                `<div class="tracker-center-grid">` +
                    `<div class="tracker-scene">` +
                        `<div class="tracker-pitch" id="trackerPitch">` +
                            `<div class="tracker-pitch-line"></div>` +
                            `<div class="tracker-pitch-circle"></div>` +
                            `<div class="tracker-pitch-dot center"></div>` +
                            `<div class="tracker-pitch-area left"></div>` +
                            `<div class="tracker-pitch-area right"></div>` +
                            `<div class="tracker-pitch-small-area left"></div>` +
                            `<div class="tracker-pitch-small-area right"></div>` +
                            `<div class="tracker-goal left"></div>` +
                            `<div class="tracker-goal right"></div>` +
                            `<div class="tracker-ball" id="trackerBall"></div>` +
                        `</div>` +
                    `</div>` +
                    `<div class="tracker-side-panel">` +
                        `<div><div class="card-title">Eventos</div><div class="tracker-feed" id="trackerEventFeed"></div></div>` +
                        `<div><div class="card-title">Momentum</div><div class="tracker-momentum" id="trackerMomentumBars"></div></div>` +
                    `</div>` +
                `</div>` +
            `</div>`
        );
    }

    function showTrackerNews(text) {
        const box = document.getElementById("trackerLiveNews");
        const value = document.getElementById("trackerLiveNewsText");
        if (!box || !value) return;
        if (trackerNewsTimer) clearTimeout(trackerNewsTimer);
        value.textContent = text;
        box.classList.add("show");
        trackerNewsTimer = setTimeout(() => box.classList.remove("show"), 3400);
    }

    function showTrackerOverlay(type, label, main, sub, duration) {
        const overlay = document.getElementById("trackerOverlay");
        const labelEl = document.getElementById("trackerOverlayLabel");
        const mainEl = document.getElementById("trackerOverlayMain");
        const subEl = document.getElementById("trackerOverlaySub");
        if (!overlay || !labelEl || !mainEl || !subEl) return;
        if (trackerOverlayTimer) clearTimeout(trackerOverlayTimer);
        overlay.className = `tracker-overlay-card ${type || "neutral"} show`;
        labelEl.textContent = label;
        mainEl.textContent = main;
        subEl.textContent = sub;
        trackerOverlayTimer = setTimeout(() => {
            overlay.className = "tracker-overlay-card";
        }, duration || 2600);
    }

    function addFeedItem(eventObj, text) {
        const feed = document.getElementById("trackerEventFeed");
        if (!feed) return;
        const title = eventObj.tipo ? eventObj.tipo.replaceAll("_", " ").toUpperCase() : "EVENTO";
        const row = document.createElement("div");
        row.className = "tracker-feed-item";
        row.innerHTML =
            `<div class="minute">${eventObj.minuto || 0}'</div>` +
            `<div class="title">${esc(title)}</div>` +
            `<div class="detail">${esc(text)}</div>`;
        feed.prepend(row);
    }

    function clockLabel(minute) {
        return `${String(clamp(minute, 0, 90)).padStart(2, "0")}:00`;
    }

    function updateProgressiveStats(match, minute) {
        const factor = clamp(minute / 90, 0, 1);
        updateTrackerStat("tracker-stat-posse", match.posse_casa || 50, (100 - (match.posse_casa || 50)).toFixed(1), "%");
        updateTrackerStat("tracker-stat-shots", Math.round((match.finalizacoes_casa || 0) * factor), Math.round((match.finalizacoes_fora || 0) * factor));
        updateTrackerStat("tracker-stat-on-target", Math.round((match.finalizacoes_gol_casa || 0) * factor), Math.round((match.finalizacoes_gol_fora || 0) * factor));
        updateTrackerStat("tracker-stat-xg", ((match.xg_casa || 0) * factor).toFixed(2), ((match.xg_fora || 0) * factor).toFixed(2));
        updateTrackerStat("tracker-stat-corners", Math.round((match.escanteios_casa || 0) * factor), Math.round((match.escanteios_fora || 0) * factor));
        updateTrackerStat("tracker-stat-fouls", Math.round((match.faltas_casa || 0) * factor), Math.round((match.faltas_fora || 0) * factor));
    }

    function resetTrackerRuntime() {
        if (matchTimer) clearInterval(matchTimer);
        if (matchData && matchData._renderLoop) clearInterval(matchData._renderLoop);
        if (matchData && matchData._matchTimer) clearInterval(matchData._matchTimer);
        if (trackerOverlayTimer) clearTimeout(trackerOverlayTimer);
        matchTimer = null;
    }

    function createTrackerState(match) {
        const homePalette = mapColors(match.time_casa, DEFAULT_HOME);
        const awayPalette = mapColors(match.time_fora, DEFAULT_AWAY);
        return {
            match,
            homePalette,
            awayPalette,
            players: buildPlayers("home", FORMATION_HOME, homePalette).concat(buildPlayers("away", FORMATION_AWAY, awayPalette)),
            ballOwner: "home-10",
            lastPossessionTeam: "home",
            ball: {
                x: 50,
                y: 50,
                targetX: 50,
                targetY: 50,
                shooting: false,
                deadBall: false,
                pass: null,
            },
            possessionHome: Number(match.posse_casa || 50),
            events: (match.eventos || []).slice().sort((a, b) => (a.minuto || 0) - (b.minuto || 0)),
            eventIndex: 0,
            scoreHome: 0,
            scoreAway: 0,
            phase: null,
            domReady: false,
        };
    }

    function attackDirection(team) {
        return team === "home" ? 1 : -1;
    }

    function findPlayer(state, playerId) {
        return state.players.find((player) => player.id === playerId) || null;
    }

    function teamPlayers(state, team, includeKeeper) {
        return state.players.filter((player) => player.team === team && (includeKeeper || player.role !== "GK"));
    }

    function weightedChoice(items, weightFn) {
        const weighted = items.map((item) => Math.max(0.1, Number(weightFn(item)) || 0.1));
        const total = weighted.reduce((sum, value) => sum + value, 0);
        let cursor = Math.random() * total;
        for (let i = 0; i < items.length; i += 1) {
            cursor -= weighted[i];
            if (cursor <= 0) return items[i];
        }
        return items[items.length - 1] || null;
    }

    function setPhase(state, type, team, duration, extra) {
        state.phase = {
            type,
            team,
            until: Date.now() + (duration || 1400),
            ...(extra || {}),
        };
    }

    function pickPassTarget(state, owner) {
        if (!owner) return null;
        const dir = attackDirection(owner.team);
        const mates = teamPlayers(state, owner.team, false).filter((player) => player.id !== owner.id);
        if (!mates.length) return null;
        return weightedChoice(mates, (player) => {
            const progress = ((player.x - owner.x) * dir) + 8;
            const spacing = Math.abs(player.y - owner.y) < 8 ? 0.8 : 1.15;
            const roleBoost = player.role === "ST" ? 1.35 : player.role.includes("W") ? 1.2 : 1;
            return Math.max(0.4, roleBoost * spacing * (0.6 + (progress / 26)));
        });
    }

    function queuePass(state, fromPlayer, toPlayer, kind) {
        if (!fromPlayer || !toPlayer) return;
        state.ballOwner = null;
        state.ball.deadBall = false;
        state.ball.pass = {
            fromId: fromPlayer.id,
            toId: toPlayer.id,
            fromX: fromPlayer.x,
            fromY: fromPlayer.y,
            toX: toPlayer.x,
            toY: toPlayer.y,
            speed: kind === "through" ? 0.16 : kind === "switch" ? 0.1 : 0.13,
            progress: 0,
        };
    }

    function chooseOwner(state, forcedTeam) {
        const team = forcedTeam || (Math.random() * 100 < state.possessionHome ? "home" : "away");
        const pool = teamPlayers(state, team, false);
        if (pool.length === 0) return;
        const owner = weightedChoice(pool, (player) => {
            const progress = team === "home" ? player.x : (100 - player.x);
            const roleBoost = player.role === "ST" ? 1.25 : player.role.includes("W") ? 1.1 : 1;
            return roleBoost * (0.7 + (progress / 55));
        });
        state.ballOwner = owner.id;
        state.lastPossessionTeam = owner.team;
        state.ball.pass = null;
        state.ball.deadBall = false;
        state.ball.targetX = owner.x + (Math.random() * 2 - 1);
        state.ball.targetY = owner.y + (Math.random() * 2 - 1);
    }

    function animateTracker(state) {
        const now = Date.now();
        if (state.phase && state.phase.until <= now) {
            if (state.phase.type === "offside") {
                chooseOwner(state, state.phase.team === "home" ? "away" : "home");
            }
            state.phase = null;
            state.ball.deadBall = false;
        }

        const phase = state.phase && state.phase.until > now ? state.phase : null;
        const owner = findPlayer(state, state.ballOwner) || findPlayer(state, `${state.lastPossessionTeam}-10`) || state.players[0];
        state.players.forEach((player) => {
            const dir = attackDirection(player.team);
            if (phase && phase.type === "corner") {
                const attacking = player.team === phase.team;
                if (player.id === phase.takerId) {
                    player.targetX = phase.cornerX;
                    player.targetY = phase.cornerY;
                } else if (player.role === "GK") {
                    player.targetX = player.team === "home" ? 6 : 94;
                    player.targetY = 50;
                } else if (attacking) {
                    player.targetX = clamp((phase.team === "home" ? 84 : 16) + ((player.number % 3) - 1) * 4, 8, 92);
                    player.targetY = clamp(18 + ((player.number * 11) % 64), 18, 82);
                } else {
                    player.targetX = clamp((phase.team === "home" ? 90 : 10) + ((player.number % 4) - 1.5) * 3, 6, 94);
                    player.targetY = clamp(20 + ((player.number * 9) % 60), 20, 80);
                }
            } else if (phase && phase.type === "penalty") {
                const attacking = player.team === phase.team;
                if (player.id === phase.takerId) {
                    player.targetX = phase.spotX - (attackDirection(phase.team) * 5);
                    player.targetY = 50;
                } else if (player.role === "GK" && !attacking) {
                    player.targetX = phase.goalX;
                    player.targetY = 50;
                } else if (player.role === "GK") {
                    player.targetX = player.team === "home" ? 6 : 94;
                    player.targetY = 50;
                } else {
                    player.targetX = attacking ? phase.spotX - (dir * 14) : phase.spotX + (dir * 12);
                    player.targetY = clamp(18 + ((player.number * 7) % 64), 18, 82);
                }
            } else if (phase && (phase.type === "foul" || phase.type === "offside")) {
                const attacking = player.team === phase.team;
                const driftX = attacking ? dir * 4 : dir * -2;
                const driftY = ((player.number % 5) - 2) * 3;
                player.targetX = clamp(player.baseX + driftX + ((phase.x - player.baseX) * (attacking ? 0.22 : 0.12)), 3, 97);
                player.targetY = clamp(player.baseY + driftY + ((phase.y - player.baseY) * 0.12), 3, 97);
            } else {
                const attackShift = owner && owner.team === player.team ? (player.team === "home" ? 3.1 : -3.1) : (player.team === "home" ? -0.9 : 0.9);
                const supportX = owner ? (owner.x - player.x) * 0.05 : 0;
                const supportY = owner ? (owner.y - player.y) * 0.03 : 0;
                player.targetX = clamp(player.baseX + attackShift + supportX, 3, 97);
                player.targetY = clamp(player.baseY + supportY + Math.sin((Date.now() / 360) + player.number) * 0.9, 3, 97);
            }
            player.x += (player.targetX - player.x) * 0.14;
            player.y += (player.targetY - player.y) * 0.14;
        });

        if (state.ball.pass) {
            state.ball.pass.progress = Math.min(1, state.ball.pass.progress + state.ball.pass.speed);
            state.ball.x = state.ball.pass.fromX + ((state.ball.pass.toX - state.ball.pass.fromX) * state.ball.pass.progress);
            state.ball.y = state.ball.pass.fromY + ((state.ball.pass.toY - state.ball.pass.fromY) * state.ball.pass.progress);
            if (state.ball.pass.progress >= 1) {
                state.ballOwner = state.ball.pass.toId;
                const receiver = findPlayer(state, state.ball.pass.toId);
                if (receiver) state.lastPossessionTeam = receiver.team;
                state.ball.pass = null;
            }
        } else if (!state.ball.shooting) {
            if (phase && phase.type === "corner") {
                state.ball.deadBall = true;
                state.ball.targetX = phase.cornerX;
                state.ball.targetY = phase.cornerY;
            } else if (phase && phase.type === "penalty") {
                state.ball.deadBall = true;
                state.ball.targetX = phase.spotX;
                state.ball.targetY = 50;
            } else if (owner) {
                state.ball.deadBall = false;
                state.ball.targetX = owner.x + (owner.team === "home" ? 2.2 : -2.2);
                state.ball.targetY = owner.y + 1.2;
            }
        }

        if (!state.ball.pass) {
            state.ball.x += (state.ball.targetX - state.ball.x) * 0.22;
            state.ball.y += (state.ball.targetY - state.ball.y) * 0.22;
        }
        syncActors(state);
    }

    function maybeQueueLivePass(state) {
        if (state.ball.shooting || state.ball.pass) return;
        if (state.phase && state.phase.until > Date.now()) return;
        const owner = findPlayer(state, state.ballOwner);
        if (!owner) return;
        const target = pickPassTarget(state, owner);
        if (!target) return;
        const kind = Math.random() < 0.18 ? "through" : Math.random() < 0.12 ? "switch" : "ground";
        queuePass(state, owner, target, kind);
    }

    function startCornerAnimation(state, team) {
        const taker = weightedChoice(teamPlayers(state, team, false), (player) => {
            return player.role.includes("W") || player.role.includes("B") ? 1.4 : player.role === "CM" ? 1.1 : 0.8;
        }) || teamPlayers(state, team, false)[0];
        const upper = Math.random() < 0.5;
        setPhase(state, "corner", team, 2200, {
            takerId: taker ? taker.id : null,
            cornerX: team === "home" ? 96 : 4,
            cornerY: upper ? 8 : 92,
        });
        if (taker) {
            state.ballOwner = taker.id;
            state.lastPossessionTeam = team;
        }
    }

    function startFoulAnimation(state, attackTeam) {
        const owner = findPlayer(state, state.ballOwner) || weightedChoice(teamPlayers(state, attackTeam, false), () => 1);
        const x = owner ? owner.x : (attackTeam === "home" ? 64 : 36);
        const y = owner ? owner.y : 50;
        setPhase(state, "foul", attackTeam, 1600, { x, y });
        state.ball.deadBall = true;
    }

    function startPenaltyAnimation(state, team) {
        const taker = weightedChoice(teamPlayers(state, team, false), (player) => {
            return player.role === "ST" ? 1.8 : player.role.includes("W") ? 1.2 : 0.9;
        }) || teamPlayers(state, team, false)[0];
        setPhase(state, "penalty", team, 2500, {
            takerId: taker ? taker.id : null,
            spotX: team === "home" ? 86 : 14,
            goalX: team === "home" ? 96 : 4,
        });
        if (taker) {
            state.ballOwner = taker.id;
            state.lastPossessionTeam = team;
        }
        state.ball.deadBall = true;
    }

    function startOffsideAnimation(state, team) {
        const runner = weightedChoice(teamPlayers(state, team, false), (player) => {
            return player.role === "ST" ? 1.7 : player.role.includes("W") ? 1.3 : 0.8;
        }) || teamPlayers(state, team, false)[0];
        const x = runner ? runner.x + (attackDirection(team) * 4) : (team === "home" ? 72 : 28);
        const y = runner ? runner.y : 50;
        setPhase(state, "offside", team, 1500, { x, y });
        state.ball.deadBall = true;
    }

    function setScore(home, away) {
        const homeEl = document.getElementById("liveScoreCasa");
        const awayEl = document.getElementById("liveScoreFora");
        if (homeEl) homeEl.textContent = home;
        if (awayEl) awayEl.textContent = away;
    }

    function moveBallToGoal(state, isHome) {
        state.ball.pass = null;
        state.ball.deadBall = false;
        state.phase = null;
        state.ballOwner = null;
        state.ball.shooting = true;
        state.ball.targetX = isHome ? 98 : 2;
        state.ball.targetY = 45 + Math.random() * 10;
        setTimeout(() => {
            state.ball.shooting = false;
        }, 650);
    }

    function processEvent(state, eventObj) {
        const isHome = eventObj.time === state.match.time_casa;
        const teamLabel = isHome ? state.homePalette.shortName : state.awayPalette.shortName;
        const baseText = eventObj.detalhe ? `${eventObj.jogador} - ${eventObj.detalhe}` : `${eventObj.jogador} - ${teamLabel}`;
        let overlayType = "neutral";
        let overlayLabel = "Evento";
        let overlayMain = "Jogo parado";
        let overlaySub = baseText;

        switch (eventObj.tipo) {
            case "gol":
            case "gol_falta":
                if (isHome) state.scoreHome += 1;
                else state.scoreAway += 1;
                setScore(state.scoreHome, state.scoreAway);
                overlayType = "goal";
                overlayLabel = eventObj.tipo === "gol_falta" ? "Gol de falta" : "Gol";
                overlayMain = "GOOOOOL!";
                overlaySub = `${eventObj.jogador} (${teamLabel}) - ${state.scoreHome} x ${state.scoreAway}`;
                moveBallToGoal(state, isHome);
                if (typeof playSound === "function") playSound(isHome ? "gol1.wav" : "goladv.wav");
                break;
            case "penalty":
                overlayType = "penalty";
                overlayLabel = "Penalti";
                overlayMain = "MARCA DA CAL";
                startPenaltyAnimation(state, isHome ? "home" : "away");
                if (typeof playSound === "function") playSound("penalty.wav");
                break;
            case "impedimento":
                overlayType = "offside";
                overlayLabel = "Impedimento";
                overlayMain = "BANDEIRA";
                startOffsideAnimation(state, isHome ? "home" : "away");
                break;
            case "cartao_amarelo":
                overlayType = "card-yellow";
                overlayLabel = "Cartao";
                overlayMain = "AMARELO";
                startFoulAnimation(state, isHome ? "away" : "home");
                break;
            case "cartao_vermelho":
                overlayType = "card-red";
                overlayLabel = "Cartao";
                overlayMain = "VERMELHO";
                startFoulAnimation(state, isHome ? "away" : "home");
                if (typeof playSound === "function") playSound("expulsao.wav");
                break;
            case "lesao":
                overlayType = "injury";
                overlayLabel = "Lesao";
                overlayMain = "ATENDIMENTO";
                if (typeof playSound === "function") playSound("contusao.wav");
                break;
            case "substituicao":
                overlayType = "sub";
                overlayLabel = "Substituicao";
                overlayMain = "MUDANCA";
                break;
            case "escanteio":
                overlayType = "foul";
                overlayLabel = "Bola parada";
                overlayMain = "ESCANTEIO";
                startCornerAnimation(state, isHome ? "home" : "away");
                break;
            case "falta":
                overlayType = "foul";
                overlayLabel = "Falta";
                overlayMain = "JOGO PARADO";
                startFoulAnimation(state, isHome ? "away" : "home");
                break;
            case "defesa_dificil":
                overlayType = "neutral";
                overlayLabel = "Defesa";
                overlayMain = "SALVA O GOLEIRO";
                chooseOwner(state, isHome ? "home" : "away");
                break;
            default:
                overlayMain = eventObj.tipo ? eventObj.tipo.replaceAll("_", " ").toUpperCase() : "EVENTO";
                break;
        }

        const liveEvent = document.getElementById("liveEvent");
        if (liveEvent) liveEvent.textContent = overlaySub;
        showTrackerOverlay(overlayType, overlayLabel, overlayMain, overlaySub, overlayType === "goal" ? 3200 : 2400);
        showTrackerNews(overlaySub);
        addFeedItem(eventObj, overlaySub);
    }

    async function finishMatch(state) {
        resetTrackerRuntime();
        updateProgressiveStats(state.match, 90);
        setScore(state.match.gols_casa || state.scoreHome, state.match.gols_fora || state.scoreAway);
        const minuteEl = document.getElementById("liveMinute");
        const eventEl = document.getElementById("liveEvent");
        if (minuteEl) minuteEl.textContent = "90:00";
        if (eventEl) eventEl.textContent = `Fim de jogo - ${state.match.placar}`;
        showTrackerOverlay("neutral", "Final", "Fim de jogo", state.match.placar, 2200);
        if (typeof playSound === "function") playSound("fimjogo.wav");
        setTimeout(async () => {
            if (typeof showResultsModal === "function") await showResultsModal();
            if (typeof checkChampionCelebration === "function") await checkChampionCelebration();
            if (typeof loadDashboard === "function") loadDashboard();
        }, 1400);
    }

    window.renderMatchView = function renderMatchView(match) {
        resetTrackerRuntime();
        matchData = match;
        const state = createTrackerState(match);
        const host = document.getElementById("partidaContent");
        if (!host) return;
        host.innerHTML = trackerMarkup(match, state.homePalette, state.awayPalette);
        renderMomentum(match.momentum);
        updateProgressiveStats(match, 0);
        setScore(0, 0);
        syncActors(state);
        matchData._trackerState = state;
    };

    window.startMatchAnimation = function startMatchAnimation(match) {
        resetTrackerRuntime();
        matchData = match;
        const state = matchData._trackerState || createTrackerState(match);
        matchData._trackerState = state;
        matchMinute = 0;
        matchLiveGoals = [0, 0];
        matchSpeed = typeof gameMatchSpeed !== "undefined" && gameMatchSpeed ? gameMatchSpeed : matchSpeed;
        chooseOwner(state);
        syncActors(state);
        showTrackerNews(`Dia de jogo: ${match.time_casa} x ${match.time_fora}`);

        function frame() {
            animateTracker(state);
            if (!state.ball.shooting && !state.ball.pass && Math.random() < 0.045) {
                maybeQueueLivePass(state);
            } else if (!state.phase && !state.ball.shooting && Math.random() < 0.01) {
                chooseOwner(state);
            }
        }

        function tick() {
            matchMinute += 1;
            const minuteEl = document.getElementById("liveMinute");
            if (minuteEl) minuteEl.textContent = clockLabel(matchMinute);
            updateProgressiveStats(match, matchMinute);

            while (state.eventIndex < state.events.length && (state.events[state.eventIndex].minuto || 0) <= matchMinute) {
                processEvent(state, state.events[state.eventIndex]);
                state.eventIndex += 1;
            }

            if (matchMinute >= 90) {
                finishMatch(state);
            }
        }

        matchData._frameFn = frame;
        matchData._tickFn = tick;
        matchData._renderLoop = setInterval(frame, 33);
        matchData._matchTimer = setInterval(tick, 1000 / matchSpeed);
        matchTimer = matchData._matchTimer;
    };
})();
