let TOKEN =
    localStorage.getItem(
        "ssh_guardian_token"
    ) || "";

let CURRENT_STREAM = null;

let STREAM_TIMER = null;


function escapeHTML(value) {
    return String(
        value ?? ""
    )
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}


function headers() {
    return {
        Authorization:
            `Bearer ${TOKEN}`,
    };
}


async function api(
    path,
    options = {},
) {
    options.headers = {
        ...headers(),
        ...(options.headers || {}),
    };

    const response = await fetch(
        path,
        options,
    );

    if (response.status === 401) {
        logout();
        throw new Error(
            "Unauthorized"
        );
    }

    if (!response.ok) {
        throw new Error(
            await response.text()
        );
    }

    return response.json();
}


function login() {
    TOKEN = document
        .getElementById("token")
        .value
        .trim();

    localStorage.setItem(
        "ssh_guardian_token",
        TOKEN,
    );

    load();
}


function logout() {
    TOKEN = "";

    localStorage.removeItem(
        "ssh_guardian_token"
    );

    document
        .getElementById("app")
        .classList.add("hidden");

    document
        .getElementById("login")
        .classList.remove("hidden");
}


async function load() {

    try {

        const [
            health,
            stats,
            events,
            bans,
            countries,
            top,
            topcountries,
            sessions,
        ] = await Promise.all([
            api("/api/health"),
            api("/api/stats"),
            api("/api/events"),
            api("/api/bans"),
            api("/api/countries"),
            api("/api/top"),
            api("/api/topcountries"),
            api("/api/sessions"),
        ]);

        document
            .getElementById("login")
            .classList.add("hidden");

        document
            .getElementById("app")
            .classList.remove("hidden");


        renderHealth(health);
        renderStats(stats);
        renderEvents(events);
        renderBans(bans);
        renderCountries(countries);
        renderTop(top);
        renderTopCountries(topcountries);
        renderSessions(sessions);

    } catch (error) {
        console.error(error);
    }
}


function renderStats(s) {

    const values = [
        [
            "Connexions",
            s.connections ?? 0,
        ],
        [
            "Échecs",
            s.failed
                ?? s.failed_logins
                ?? 0,
        ],
        [
            "Succès",
            s.success
                ?? s.successful_logins
                ?? 0,
        ],
        [
            "IP uniques",
            s.unique_ips ?? 0,
        ],
        [
            "Bans",
            s.bans ?? 0,
        ],
        [
            "Événements",
            s.events
                ?? s.total_events
                ?? 0,
        ],
    ];


    document
        .getElementById("stats")
        .innerHTML = values.map(
            ([label, value]) => `
            <div class="stat">
                <span>${label}</span>
                <strong>${value}</strong>
            </div>
        `
        ).join("");
}


function renderHealth(data) {

    const entries =
        Object.entries(
            data.services || {}
        );


    document
        .getElementById("services")
        .innerHTML = entries.map(
            ([name, status]) => `
            <div class="service">

                <span>
                    ${escapeHTML(name)}
                </span>

                <strong class="${
                    status === "active"
                        ? "ok"
                        : "bad"
                }">
                    ${escapeHTML(status)}
                </strong>

            </div>
        `
        ).join("");


    const allOk =
        data.redis
        && entries.every(
            ([, status]) =>
                status === "active"
        );


    document
        .getElementById(
            "global-status"
        )
        .innerHTML = allOk
            ? '<span class="ok">● Système opérationnel</span>'
            : '<span class="bad">● Système dégradé</span>';
}


function renderSessions(sessions) {

    const box =
        document.getElementById(
            "sessions"
        );


    if (!sessions.length) {

        box.innerHTML =
            '<div class="empty">Aucune session SSH active</div>';

        return;
    }


    box.innerHTML = sessions.map(
        s => `

        <div class="session-card">

            <div class="session-main">

                <strong>
                    👤 ${escapeHTML(s.user)}
                </strong>

                <span>
                    🌐 ${
                        escapeHTML(
                            s.remote_ip
                            || "IP inconnue"
                        )
                    }
                </span>

                <span>
                    PID ${s.pid}
                </span>

                <span>
                    ${escapeHTML(s.tty)}
                </span>

                ${
                    s.streamable
                    ? '<span class="ok">● STREAMABLE</span>'
                    : '<span class="bad">● PAS DE RECORDER</span>'
                }

            </div>


            <div class="session-actions">

                ${
                    s.streamable
                    ? `
                    <button
                        onclick="startStream(
                            '${s.session_id}',
                            '${s.pid}'
                        )"
                    >
                        📡 Stream
                    </button>
                    `
                    : ""
                }

                <button
                    class="danger"
                    onclick="killSession(
                        '${s.pid}'
                    )"
                >
                    💥 Kill
                </button>

            </div>

        </div>
    `
    ).join("");
}


async function startStream(
    sessionId,
    pid,
) {

    const result = await api(
        `/api/stream/start/${sessionId}?lines=30`,
        {
            method: "POST",
        },
    );


    if (!result.ok) {
        alert(
            result.error
            || "Impossible de démarrer le stream"
        );

        return;
    }


    CURRENT_STREAM = {
        streamId:
            result.stream_id,

        sessionId:
            sessionId,

        pid:
            pid,
    };


    document
        .getElementById(
            "stream-info"
        )
        .textContent =
            `Session ${sessionId} — PID ${pid}`;


    document
        .getElementById(
            "stream-output"
        )
        .textContent =
            "Connexion au terminal...";


    document
        .getElementById(
            "stream-modal"
        )
        .classList.remove(
            "hidden"
        );


    STREAM_TIMER =
        setInterval(
            refreshStream,
            700,
        );


    await refreshStream();
}


async function refreshStream() {

    if (!CURRENT_STREAM) {
        return;
    }


    try {

        const data = await api(
            `/api/stream/${CURRENT_STREAM.streamId}`
        );


        if (!data.ok) {
            return;
        }


        document
            .getElementById(
                "stream-output"
            )
            .textContent =
                data.content
                || "(Attente...)";


        if (!data.alive) {

            document
                .getElementById(
                    "stream-info"
                )
                .textContent +=
                    " — TERMINÉE";

            clearInterval(
                STREAM_TIMER
            );

            STREAM_TIMER = null;
        }

    } catch (error) {
        console.error(error);
    }
}


async function stopStream() {

    if (!CURRENT_STREAM) {
        return;
    }


    await api(
        `/api/stream/stop/${CURRENT_STREAM.streamId}`,
        {
            method: "POST",
        },
    );


    closeStream();
}


function closeStream() {

    if (STREAM_TIMER) {
        clearInterval(
            STREAM_TIMER
        );
    }


    STREAM_TIMER = null;

    CURRENT_STREAM = null;


    document
        .getElementById(
            "stream-modal"
        )
        .classList.add(
            "hidden"
        );
}


async function killStreamSession() {

    if (!CURRENT_STREAM) {
        return;
    }


    if (!confirm(
        "Tuer cette session SSH ?"
    )) {
        return;
    }


    await killSession(
        CURRENT_STREAM.pid
    );

    closeStream();
}


async function killSession(pid) {

    if (!confirm(
        `Tuer la session ${pid} ?`
    )) {
        return;
    }


    await api(
        `/api/kill-session/${pid}`,
        {
            method: "POST",
        },
    );


    await load();
}


async function killAllSessions() {

    if (!confirm(
        "Tuer TOUTES les sessions SSH distantes ?"
    )) {
        return;
    }


    await api(
        "/api/kill-all-sessions",
        {
            method: "POST",
        },
    );


    await load();
}


function renderEvents(events) {

    document
        .getElementById("events")
        .innerHTML = events.map(
            e => `

        <tr>

            <td>
                ${escapeHTML(e.event_type)}
            </td>

            <td>
                <code>${escapeHTML(e.ip)}</code>
            </td>

            <td>
                ${escapeHTML(e.username)}
            </td>

            <td>
                ${escapeHTML(e.city)}
                ${
                    e.country
                    ? ", "
                    + escapeHTML(
                        e.country
                    )
                    : ""
                }
            </td>

            <td>
                ${escapeHTML(e.isp)}
            </td>

            <td>
                ${escapeHTML(e.timestamp)}
            </td>

        </tr>

    `
        ).join("");
}


function renderBans(bans) {

    const box =
        document.getElementById(
            "bans"
        );


    if (!bans.length) {

        box.innerHTML =
            '<div class="empty">Aucun ban actif</div>';

        return;
    }


    box.innerHTML =
        bans.map(
            ban => `

        <div class="ban">

            <div>

                <strong>
                    ${escapeHTML(ban.ip)}
                </strong>

                <br>

                <small>
                    ${
                        escapeHTML(
                            ban.reason
                            || "security"
                        )
                    }
                </small>

            </div>


            <button
                class="danger"
                onclick="unban(
                    '${escapeHTML(ban.ip)}'
                )"
            >
                Unban
            </button>

        </div>

    `
        ).join("");
}


async function unban(ip) {

    await api(
        `/api/unban/${ip}`,
        {
            method: "POST",
        },
    );

    await load();
}


function renderCountries(data) {

    const countries =
        data.blocked_countries
        || [];


    document
        .getElementById(
            "countries"
        )
        .innerHTML =
            countries.length
            ? countries.map(
                code => `

                <span class="tag">

                    ${escapeHTML(code)}

                    <button
                        onclick="unblockCountry(
                            '${escapeHTML(code)}'
                        )"
                    >
                        ×
                    </button>

                </span>

            `
            ).join("")
            : "Aucun pays bloqué";
}


async function blockCountry() {

    const input =
        document.getElementById(
            "country"
        );


    const country =
        input.value
        .trim()
        .toLowerCase();


    if (!country) {
        return;
    }


    await api(
        `/api/block-country/${country}`,
        {
            method: "POST",
        },
    );


    input.value = "";

    await load();
}


async function unblockCountry(
    country,
) {

    await api(
        `/api/unblock-country/${country}`,
        {
            method: "POST",
        },
    );


    await load();
}


function renderTop(data) {

    document
        .getElementById("top")
        .innerHTML = data.map(
            (x, index) => `

        <div class="row">

            <span>
                ${index + 1}.
                <code>
                    ${escapeHTML(x.ip)}
                </code>

                <small>
                    ${escapeHTML(x.country)}
                </small>
            </span>

            <strong>
                ${x.attempts}
            </strong>

        </div>

    `
        ).join("");
}


function renderTopCountries(data) {

    document
        .getElementById(
            "topcountries"
        )
        .innerHTML = data.map(
            (x, index) => `

        <div class="row">

            <span>
                ${index + 1}.
                ${escapeHTML(x.country)}
                ${
                    x.country_code
                    ? `(${escapeHTML(x.country_code)})`
                    : ""
                }
            </span>

            <strong>
                ${x.attempts}
            </strong>

        </div>

    `
        ).join("");
}


async function searchIP() {

    const ip =
        document
        .getElementById(
            "search-ip"
        )
        .value
        .trim();


    if (!ip) {
        return;
    }


    const data = await api(
        `/api/search/${encodeURIComponent(ip)}`
    );


    const box =
        document.getElementById(
            "search-results"
        );


    if (!data.events.length) {

        box.innerHTML =
            "Aucun événement trouvé.";

        return;
    }


    box.innerHTML = `

        <h3>
            ${escapeHTML(ip)}
        </h3>

        <div class="search-list">

        ${
            data.events.map(
                e => `

            <div class="search-event">

                <strong>
                    ${escapeHTML(e.event_type)}
                </strong>

                <span>
                    ${escapeHTML(e.timestamp)}
                </span>

                <span>
                    ${escapeHTML(e.city)},
                    ${escapeHTML(e.country)}
                </span>

            </div>

        `
            ).join("")
        }

        </div>
    `;
}


if (TOKEN) {
    load();
}


setInterval(
    () => {

        if (
            TOKEN
            && !CURRENT_STREAM
        ) {
            load();
        }

    },
    5000,
);
