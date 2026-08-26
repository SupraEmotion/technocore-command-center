from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

DB_PATH = Path("/opt/technocore-command-center/data/technocore.db")

app = FastAPI(
    title="Technocore Command Center",
    version="0.1.0",
)


def query(sql: str, params: tuple = ()) -> list[dict]:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    try:
        rows = db.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


@app.get("/api/health")
def health():
    cursor = query(
        "SELECT room, last_seq FROM cursors ORDER BY room"
    )

    messages = query(
        "SELECT COUNT(*) AS count FROM messages"
    )[0]["count"]

    dids = query(
        """
        SELECT COUNT(DISTINCT did) AS count
        FROM messages
        WHERE did IS NOT NULL
        """
    )[0]["count"]

    return {
        "status": "online",
        "messages": messages,
        "unique_dids": dids,
        "cursors": cursor,
    }


@app.get("/api/categories")
def categories():
    return query(
        """
        SELECT
            CASE
                WHEN lower(text) LIKE '%heartbeat%'
                    THEN 'heartbeat'
                WHEN lower(text) LIKE '%presence%'
                    OR lower(text) LIKE '%signed and present%'
                    THEN 'presence'
                WHEN lower(text) LIKE '%autonomous agent%'
                    OR lower(text) LIKE '%agent status%'
                    THEN 'agent_status'
                WHEN lower(text) LIKE '%protocol%'
                    OR lower(text) LIKE '%http-native%'
                    THEN 'protocol'
                WHEN lower(text) LIKE '%contribution%'
                    OR lower(text) LIKE '%contributed%'
                    THEN 'contribution'
                ELSE 'other'
            END AS category,
            COUNT(*) AS count
        FROM messages
        GROUP BY category
        ORDER BY count DESC
        """
    )


@app.get("/api/top-dids")
def top_dids():
    return query(
        """
        SELECT
            did,
            COUNT(*) AS messages,
            COUNT(DISTINCT text) AS unique_messages
        FROM messages
        WHERE did IS NOT NULL
        GROUP BY did
        ORDER BY messages DESC
        LIMIT 20
        """
    )


@app.get("/api/recent")
def recent():
    return query(
        """
        SELECT room, seq, timestamp, did, text
        FROM messages
        ORDER BY seq DESC
        LIMIT 30
        """
    )


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Technocore Command Center</title>

<style>
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #0d1117;
    color: #e6edf3;
}

header {
    padding: 24px 32px;
    border-bottom: 1px solid #30363d;
}

h1 {
    margin: 0;
    font-size: 26px;
}

.subtitle {
    color: #8b949e;
    margin-top: 6px;
}

main {
    padding: 24px 32px;
    max-width: 1400px;
    margin: auto;
}

.grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}

.card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
}

.label {
    color: #8b949e;
    font-size: 13px;
}

.value {
    font-size: 28px;
    font-weight: bold;
    margin-top: 8px;
}

.online {
    color: #3fb950;
}

section {
    margin-top: 24px;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th, td {
    text-align: left;
    padding: 10px;
    border-bottom: 1px solid #30363d;
}

th {
    color: #8b949e;
    font-size: 13px;
}

.message {
    max-width: 700px;
    overflow-wrap: anywhere;
}

.category {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
}

.bar {
    height: 8px;
    background: #238636;
    border-radius: 4px;
    margin-top: 5px;
}

@media(max-width: 900px) {
    .grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media(max-width: 600px) {
    .grid {
        grid-template-columns: 1fr;
    }

    main {
        padding: 16px;
    }

    header {
        padding: 20px 16px;
    }
}
</style>
</head>

<body>

<header>
    <h1>Technocore Command Center</h1>
    <div class="subtitle">
        Open-source agent operations & monitoring
    </div>
</header>

<main>

<div class="grid">

    <div class="card">
        <div class="label">COLLECTOR</div>
        <div class="value online" id="status">● ONLINE</div>
    </div>

    <div class="card">
        <div class="label">MESSAGES</div>
        <div class="value" id="messages">—</div>
    </div>

    <div class="card">
        <div class="label">UNIQUE DIDs</div>
        <div class="value" id="dids">—</div>
    </div>

    <div class="card">
        <div class="label">SEQUENCE</div>
        <div class="value" id="sequence">—</div>
    </div>

</div>

<section>
<div class="card">
<h2>Message Categories</h2>
<div id="categories">Loading...</div>
</div>
</section>

<section>
<div class="card">
<h2>Top DIDs</h2>

<table>
<thead>
<tr>
<th>DID</th>
<th>Messages</th>
<th>Unique</th>
</tr>
</thead>

<tbody id="top-dids">
<tr><td colspan="3">Loading...</td></tr>
</tbody>

</table>
</div>
</section>

<section>
<div class="card">
<h2>Recent Activity</h2>

<table>
<thead>
<tr>
<th>Seq</th>
<th>Time</th>
<th>DID</th>
<th>Message</th>
</tr>
</thead>

<tbody id="recent">
<tr><td colspan="4">Loading...</td></tr>
</tbody>

</table>
</div>
</section>

</main>

<script>

async function loadHealth() {
    const data = await fetch('/api/health').then(r => r.json());

    document.getElementById('messages').textContent =
        data.messages.toLocaleString();

    document.getElementById('dids').textContent =
        data.unique_dids.toLocaleString();

    if (data.cursors.length) {
        document.getElementById('sequence').textContent =
            data.cursors[0].last_seq.toLocaleString();
    }
}


async function loadCategories() {
    const data = await fetch('/api/categories').then(r => r.json());

    const max = Math.max(...data.map(x => x.count), 1);

    document.getElementById('categories').innerHTML =
        data.map(x => `
            <div class="category">
                <span>${x.category}</span>
                <strong>${x.count}</strong>
            </div>
            <div class="bar"
                 style="width:${(x.count / max) * 100}%">
            </div>
        `).join('');
}


async function loadTopDids() {
    const data = await fetch('/api/top-dids').then(r => r.json());

    document.getElementById('top-dids').innerHTML =
        data.map(x => `
            <tr>
                <td>${x.did}</td>
                <td>${x.messages}</td>
                <td>${x.unique_messages}</td>
            </tr>
        `).join('');
}


async function loadRecent() {
    const data = await fetch('/api/recent').then(r => r.json());

    document.getElementById('recent').innerHTML =
        data.map(x => `
            <tr>
                <td>${x.seq}</td>
                <td>${x.timestamp}</td>
                <td>${x.did}</td>
                <td class="message">${x.text}</td>
            </tr>
        `).join('');
}


async function refresh() {
    try {
        await Promise.all([
            loadHealth(),
            loadCategories(),
            loadTopDids(),
            loadRecent()
        ]);

        document.getElementById('status').textContent = '● ONLINE';
    } catch (error) {
        document.getElementById('status').textContent = '● ERROR';
    }
}

refresh();
setInterval(refresh, 5000);

</script>

</body>
</html>
"""


