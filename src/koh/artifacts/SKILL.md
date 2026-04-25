---
name: koh-game-loop
description: Use when an AI agent needs to autonomously complete the Asuri Major competition game loop — authenticating, submitting models, setting BP preferences, monitoring rounds and matches, and viewing results via HTTP API without browser interaction.
---

# Asuri Major Game Loop — Autonomous Agent API Reference

## Overview

This skill covers the **complete player workflow** via HTTP API. Game rules and environment details live in downloadable artifacts; concrete map files should be obtained from the map detail page when needed.

**Do NOT hardcode game rules from memory. Always fetch the authoritative documents.**

---

## Step 0 — Download Authoritative Artifacts

All rules and environment code are served by the competition host. Replace `<BASE>` with the actual host URL.

| Artifact | URL | Use |
|----------|-----|-----|
| Competition rules | `GET <BASE>/api/artifacts/KOH_rules.md` | Scoring, win conditions, constraints |
| Game environment | `GET <BASE>/api/artifacts/koh_env.py` | `KOHBattleEnv` simulation class |
| Baseline template | `GET <BASE>/api/artifacts/koh_baseline_template.py` | Starter training code |

```python
import requests, pathlib

BASE = "http://<competition-host>"

for name, url in [
    ("KOH_rules.md",              f"{BASE}/api/artifacts/KOH_rules.md"),
    ("koh_env.py",                f"{BASE}/api/artifacts/koh_env.py"),
    ("koh_baseline_template.py",  f"{BASE}/api/artifacts/koh_baseline_template.py"),
]:
    data = requests.get(url).content
    pathlib.Path(name).write_bytes(data)
    print(f"saved {name} ({len(data)} bytes)")
```

---

## Step 1 — Authenticate

```python
# Register (only if account doesn't exist; invite_token optional)
requests.post(f"{BASE}/api/auth/register",
              json={"username": "bot", "password": "...", "invite_token": "..."})

# Login → get Bearer token
r = requests.post(f"{BASE}/api/auth/login",
                  json={"username": "bot", "password": "..."})
token = r.json()["data"]["token"]
H = {"Authorization": f"Bearer {token}"}

# Verify
me = requests.get(f"{BASE}/api/auth/me", headers=H).json()["data"]
print(me)  # {id, username, is_admin, elo}
```

All subsequent calls require `Authorization: Bearer <token>`.

---

## Step 2 — Check Competition Status

```python
status = requests.get(f"{BASE}/api/status", headers=H).json()["data"]
# {current_round_id, next_round_id, next_round_at, maps, version}
print(status)
```

---

## Step 3 — Upload Models

Upload **attack** and **defense** `.safetensors` files separately. 5-second cooldown between uploads.

```python
import time

for role, path in [("attack", "attack_model.safetensors"),
                   ("defense", "defense_model.safetensors")]:
    with open(path, "rb") as f:
        r = requests.post(f"{BASE}/api/submissions",
                          headers=H,
                          data={"role": role},
                          files={"file": (path, f)})
    print(role, r.json())
    time.sleep(6)  # respect 5s cooldown
```

Constraints: `.safetensors` only · max 50 MB per file.

---

## Step 4 — Set Map Preferences (BP)

Get the round's maps first, then submit preferences (ordered list of map indices to prioritize).

```python
# Get current round maps
round_id = status["current_round_id"]
maps = requests.get(f"{BASE}/api/rounds/{round_id}/maps", headers=H).json()["data"]
map_indices = [m["map_idx"] for m in maps]
print(map_indices)  # e.g. [0, 1, 2]

# Submit preference (index order = preference order)
requests.post(f"{BASE}/api/bp",
              headers={**H, "Content-Type": "application/json"},
              json={"map_preferences": map_indices})
```

---

## Step 5 — Monitor Round Progress

### Poll via HTTP

```python
import time

while True:
    matches = requests.get(f"{BASE}/api/rounds/{round_id}/matches", headers=H).json()["data"]
    by_status = {}
    for m in matches:
        by_status.setdefault(m["status"], 0)
        by_status[m["status"]] += 1
    print(by_status)
    if by_status.get("queued", 0) == 0 and by_status.get("running", 0) == 0:
        break
    time.sleep(10)
```

### WebSocket (real-time push)

```python
import websocket, json

def on_message(ws, msg):
    payload = json.loads(msg)
    if payload["type"] == "round_live":
        print(payload["data"])  # {total, queued, running, completed, failed}

ws = websocket.WebSocketApp(
    f"ws://<competition-host>/ws/rounds/{round_id}/live",
    on_message=on_message,
)
ws.run_forever()
```

---

## Step 6 — View Results

```python
# All matches in round
matches = requests.get(f"{BASE}/api/rounds/{round_id}/matches", headers=H).json()["data"]

# Single match detail + which models were used
match = requests.get(f"{BASE}/api/matches/{match_id}", headers=H).json()["data"]

# Frame-by-frame replay
replay = requests.get(f"{BASE}/api/matches/{match_id}/replay", headers=H).json()["data"]

# ELO history
elo = requests.get(f"{BASE}/api/users/{me['username']}/elo-history", headers=H).json()["data"]

# Leaderboard
lb = requests.get(f"{BASE}/api/leaderboard", headers=H).json()["data"]
```

---

## Admin Operations (requires admin account)

```python
# Create a new round
r = requests.post(f"{BASE}/api/admin/rounds",
                  headers={**H, "Content-Type": "application/json"},
                  json={"auto_run": True})
round_id = r.json()["data"]["id"]

# Trigger pipeline (closes submissions, queues matches)
requests.post(f"{BASE}/api/admin/rounds/{round_id}/pipeline", headers=H)

# Finalize round (settle ELO after all matches complete)
requests.post(f"{BASE}/api/admin/rounds/{round_id}/finalize", headers=H)

# System health
health = requests.get(f"{BASE}/api/admin/system", headers=H).json()["data"]
# {db, redis, celery_workers, celery_active_tasks}

# Retry a failed match
requests.post(f"{BASE}/api/admin/matches/{match_id}/retry", headers=H)

# Reset all failed matches in a round
requests.post(f"{BASE}/api/admin/rounds/{round_id}/reset-failed", headers=H)
```

---

## Full API Quick Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Register `{username, password, invite_token?}` |
| POST | `/api/auth/login` | — | Login → `{token, expires_at}` |
| GET | `/api/auth/me` | ✓ | Current user + ELO |
| GET | `/api/status` | ✓ | Service status, current/next round |
| GET | `/api/leaderboard` | ✓ | All users sorted by ELO |
| GET | `/api/rounds?limit=50` | ✓ | Recent rounds list |
| GET | `/api/rounds/{id}/maps` | ✓ | Maps for a round |
| GET | `/api/rounds/{id}/matches` | ✓ | Matches in a round |
| GET | `/api/matches/{id}` | ✓ | Match detail + models used |
| GET | `/api/matches/{id}/replay` | ✓ | Frame-by-frame replay JSON |
| GET | `/api/users/{name}/elo-history` | ✓ | ELO history by round |
| POST | `/api/submissions` | ✓ | Upload model (multipart: `role`, `file`) |
| GET | `/api/submissions` | ✓ | Your submissions (newest first) |
| GET | `/api/submissions/{id}/download` | ✓ | Download your file |
| POST | `/api/bp` | ✓ | Set map preferences `{map_preferences: [int]}` |
| GET | `/api/bp` | ✓ | Get your map preferences |
| WS | `/ws/rounds/{id}/live` | — | Real-time round match counts |
| GET | `/api/artifacts/KOH_rules.md` | — | **Official rules document** |
| GET | `/api/artifacts/koh_env.py` | — | Game environment source |
| GET | `/api/artifacts/koh_baseline_template.py` | — | Baseline training template |
| POST | `/api/admin/rounds` | admin | Create round |
| POST | `/api/admin/rounds/{id}/pipeline` | admin | Close & queue matches |
| POST | `/api/admin/rounds/{id}/finalize` | admin | Settle ELO |
| GET | `/api/admin/system` | admin | DB/Redis/Celery health |
| POST | `/api/admin/matches/{id}/retry` | admin | Retry failed match |
| POST | `/api/admin/rounds/{id}/reset-failed` | admin | Bulk-retry failed matches |

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `HTTP 401` | Token expired / missing | Re-login |
| `upload cooldown: wait Xs` | Too fast | `time.sleep(6)` between uploads |
| `only .safetensors files accepted` | Wrong format | Use `safetensors.torch.save_file` |
| `invalid weights: ...` | Architecture mismatch | Download `koh_env.py` and check `DQN` spec |
| `registration is disabled` | No open registration | Use invite token |
