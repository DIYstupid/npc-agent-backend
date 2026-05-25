# API Contract

Updated: 2026-05-25

This document freezes the current Python Agent Runtime contract before the
Go API Service is added. It records the externally relevant HTTP and SSE
behavior that downstream clients should keep relying on.

Base URL for local development:

```text
http://127.0.0.1:8000
```

## Common Rules

- Request and response bodies are JSON unless an endpoint explicitly returns
  `text/event-stream`.
- Resource IDs are non-empty strings with at most 64 characters and must match
  the backend `ResourceId` validation pattern.
- Validation errors use HTTP `422`.
- Application errors use a stable envelope:

```json
{
  "error": {
    "code": "player_not_found",
    "message": "player not found: missing_player",
    "details": {
      "resource": "player",
      "identifier": "missing_player"
    }
  }
}
```

Common error examples:

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
```

```json
{
  "error": {
    "code": "npc_not_found",
    "message": "npc not found: missing_npc",
    "details": {
      "resource": "npc",
      "identifier": "missing_npc"
    }
  }
}
```

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json
```

```json
{
  "error": {
    "code": "request_validation_error",
    "message": "Request validation failed",
    "details": [
      {
        "type": "missing",
        "loc": ["body", "message"],
        "msg": "Field required",
        "input": {"player_id": "player_001"}
      }
    ]
  }
}
```

## Health

### `GET /health`

Returns process-level health for the Python runtime.

Request:

```bash
curl http://127.0.0.1:8000/health
```

Response:

```json
{
  "status": "ok",
  "service": "npc-agent-backend",
  "version": "0.5.0"
}
```

## NPCs

### `GET /npcs`

Lists all configured NPC profiles.

Request:

```bash
curl http://127.0.0.1:8000/npcs
```

Response:

```json
[
  {
    "npc_id": "blacksmith_001",
    "name": "Glen",
    "role": "Blacksmith",
    "personality": "Blunt but loyal",
    "faction": "village",
    "goal": "Recover the missing apprentice and repair village weapons",
    "location": "blacksmith_shop",
    "relationship": {}
  }
]
```

### `GET /npcs/{npc_id}`

Returns one NPC profile.

Request:

```bash
curl http://127.0.0.1:8000/npcs/blacksmith_001
```

Response: same object shape as one item from `GET /npcs`.

Error:

```json
{
  "error": {
    "code": "npc_not_found",
    "message": "npc not found: missing_npc",
    "details": {
      "resource": "npc",
      "identifier": "missing_npc"
    }
  }
}
```

## Game State

### `GET /game/state/{player_id}`

Returns the current player state.

Request:

```bash
curl http://127.0.0.1:8000/game/state/player_001
```

Response:

```json
{
  "player_id": "player_001",
  "name": "Gary",
  "location": "village_square",
  "inventory": ["old_sword", "bread"],
  "active_quests": ["investigate_wolves"],
  "completed_quests": [],
  "quest_progress": {},
  "world_flags": {
    "wolves_near_village": true,
    "mine_unlocked": false
  },
  "relationships": {
    "blacksmith_001": 0,
    "healer_001": 0,
    "guard_001": 0
  }
}
```

Error:

```json
{
  "error": {
    "code": "player_not_found",
    "message": "player not found: missing_player",
    "details": {
      "resource": "player",
      "identifier": "missing_player"
    }
  }
}
```

## Chat

### `POST /chat/{npc_id}`

Runs a synchronous NPC chat turn.

Request:

```bash
curl -X POST http://127.0.0.1:8000/chat/blacksmith_001 \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"player_001\",\"message\":\"Any news about the wolves?\"}"
```

Request body:

```json
{
  "player_id": "player_001",
  "message": "Any news about the wolves?"
}
```

Response:

```json
{
  "npc_id": "blacksmith_001",
  "player_id": "player_001",
  "reply": "Keep your blade close. The guard has seen tracks near the north road.",
  "actions": [
    {
      "tool": "update_relationship",
      "args": {
        "npc_id": "blacksmith_001",
        "delta": 1
      }
    }
  ],
  "executed_actions": [
    {
      "tool": "update_relationship",
      "success": true,
      "message": "relationship updated",
      "data": {
        "npc_id": "blacksmith_001"
      }
    }
  ],
  "context_report": {
    "request_id": "9b3d1ef3-4020-4339-a8fe-1ef90a010101",
    "prompt_token_estimate": 1200,
    "prompt_token_budget": 3000,
    "selected_short_term_count": 4,
    "selected_long_term_count": 3,
    "selected_shared_knowledge_count": 1,
    "saved_token_estimate": 250
  }
}
```

Errors:

- `404 npc_not_found`
- `404 player_not_found`
- `422 request_validation_error`
- `500 internal_error`

### `POST /chat/{npc_id}/stream`

Runs the same chat pipeline as `POST /chat/{npc_id}` and streams the response
as Server-Sent Events.

Request:

```bash
curl -N -X POST http://127.0.0.1:8000/chat/blacksmith_001/stream \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"player_001\",\"message\":\"Any news about the wolves?\"}"
```

Response headers:

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream; charset=utf-8
Cache-Control: no-cache
X-Accel-Buffering: no
```

Normal event order:

```text
start -> delta* -> final
```

Normal stream example:

```text
event: start
data: {"request_id":"9b3d1ef3-4020-4339-a8fe-1ef90a010101","npc_id":"blacksmith_001","player_id":"player_001"}

event: delta
data: {"text":"K"}

event: delta
data: {"text":"e"}

event: final
data: {"npc_id":"blacksmith_001","player_id":"player_001","reply":"Keep your blade close.","actions":[],"executed_actions":[],"context_report":null}
```

Error event contract:

```text
event: error
data: {"request_id":"9b3d1ef3-4020-4339-a8fe-1ef90a010101","message":"error detail"}
```

Errors raised before the stream starts, such as missing NPC or player, use the
standard JSON error envelope. Errors raised inside the streaming pipeline are
sent as the `error` SSE event shown above.

## Long-Term Memory

### `POST /memory/long-term`

Creates one long-term memory record.

Request:

```bash
curl -X POST http://127.0.0.1:8000/memory/long-term \
  -H "Content-Type: application/json" \
  -d "{\"npc_id\":\"blacksmith_001\",\"player_id\":\"player_001\",\"text\":\"Player found wolf tracks.\",\"importance\":8,\"memory_type\":\"quest\",\"tags\":[\"wolves\"]}"
```

Request body:

```json
{
  "npc_id": "blacksmith_001",
  "player_id": "player_001",
  "text": "Player found wolf tracks.",
  "importance": 8,
  "memory_type": "quest",
  "tags": ["wolves"]
}
```

Response:

```json
{
  "memory_id": "3d3e7b10-bf5e-4dd0-a88a-1df7f9d01010",
  "npc_id": "blacksmith_001",
  "player_id": "player_001",
  "text": "Player found wolf tracks.",
  "memory_type": "quest",
  "importance": 8,
  "created_at": "2026-05-25T10:00:00Z",
  "tags": ["wolves"]
}
```

### `GET /memory/long-term`

Lists long-term memories for one NPC/player pair.

Query parameters:

- `npc_id`: required
- `player_id`: required
- `memory_type`: optional
- `limit`: optional, `1..100`, default `50`

Request:

```bash
curl "http://127.0.0.1:8000/memory/long-term?npc_id=blacksmith_001&player_id=player_001&limit=10"
```

Response:

```json
{
  "npc_id": "blacksmith_001",
  "player_id": "player_001",
  "memories": [
    {
      "memory_id": "3d3e7b10-bf5e-4dd0-a88a-1df7f9d01010",
      "npc_id": "blacksmith_001",
      "player_id": "player_001",
      "text": "Player found wolf tracks.",
      "memory_type": "quest",
      "importance": 8,
      "created_at": "2026-05-25T10:00:00Z",
      "tags": ["wolves"]
    }
  ]
}
```

Related endpoints:

- `GET /memory/long-term/search`
- `PATCH /memory/long-term/{memory_id}`
- `DELETE /memory/long-term/{memory_id}`
- `GET /memory/summary/{player_id}/{npc_id}`

## Shared Knowledge

### `POST /knowledge/events`

Creates a shared knowledge event.

Request:

```bash
curl -X POST http://127.0.0.1:8000/knowledge/events \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Wolves were seen near the north road.\",\"player_id\":\"player_001\",\"world_id\":\"default\",\"scope\":\"player\",\"known_by_npc_ids\":[\"guard_001\"],\"event_type\":\"rumor\",\"confidence\":0.8,\"tags\":[\"wolves\"]}"
```

Request body:

```json
{
  "text": "Wolves were seen near the north road.",
  "player_id": "player_001",
  "world_id": "default",
  "scope": "player",
  "related_player_ids": [],
  "source_npc_id": "guard_001",
  "subject_npc_ids": ["guard_001"],
  "known_by_npc_ids": ["guard_001"],
  "location": "north_road",
  "event_type": "rumor",
  "confidence": 0.8,
  "status": "active",
  "expires_at": null,
  "tags": ["wolves"]
}
```

Response:

```json
{
  "event_id": "0c17c27c-9c8e-4cc0-923f-8ea8f0010101",
  "world_id": "default",
  "scope": "player",
  "player_id": "player_001",
  "related_player_ids": [],
  "text": "Wolves were seen near the north road.",
  "source_npc_id": "guard_001",
  "subject_npc_ids": ["guard_001"],
  "known_by_npc_ids": ["guard_001"],
  "location": "north_road",
  "event_type": "rumor",
  "confidence": 0.8,
  "status": "active",
  "created_at": "2026-05-25T10:00:00Z",
  "expires_at": null,
  "tags": ["wolves"]
}
```

### `GET /knowledge/events`

Lists shared knowledge visible under the supplied filters.

Query parameters:

- `world_id`: optional, default `default`
- `player_id`: optional
- `npc_id`: optional
- `status`: optional, default `active`
- `event_type`: optional
- `limit`: optional, `1..100`, default `50`

Request:

```bash
curl "http://127.0.0.1:8000/knowledge/events?world_id=default&player_id=player_001&npc_id=guard_001"
```

Response:

```json
{
  "events": [
    {
      "event_id": "0c17c27c-9c8e-4cc0-923f-8ea8f0010101",
      "world_id": "default",
      "scope": "player",
      "player_id": "player_001",
      "related_player_ids": [],
      "text": "Wolves were seen near the north road.",
      "source_npc_id": "guard_001",
      "subject_npc_ids": ["guard_001"],
      "known_by_npc_ids": ["guard_001"],
      "location": "north_road",
      "event_type": "rumor",
      "confidence": 0.8,
      "status": "active",
      "created_at": "2026-05-25T10:00:00Z",
      "expires_at": null,
      "tags": ["wolves"]
    }
  ]
}
```

Related endpoints:

- `GET /knowledge/events/{event_id}`
- `PATCH /knowledge/events/{event_id}`
- `POST /knowledge/events/{event_id}/known-by/{npc_id}`
- `POST /knowledge/events/{event_id}/resolve`

## World Interactions

### `POST /world/interactions`

Parses and applies a natural-language player interaction with the world.

Request:

```bash
curl -X POST http://127.0.0.1:8000/world/interactions \
  -H "Content-Type: application/json" \
  -d "{\"player_id\":\"player_001\",\"text\":\"I inspect the wolf tracks near the north road.\",\"world_id\":\"default\",\"location\":\"north_road\",\"npc_id\":\"guard_001\"}"
```

Request body:

```json
{
  "player_id": "player_001",
  "text": "I inspect the wolf tracks near the north road.",
  "world_id": "default",
  "location": "north_road",
  "npc_id": "guard_001"
}
```

Response:

```json
{
  "request_id": "c7b0e5c4-e04b-4c49-b81d-1bdf00010101",
  "world_id": "default",
  "player_id": "player_001",
  "status": "ok",
  "message": "interaction applied",
  "parsed_actions": [
    {
      "player_id": "player_001",
      "action_type": "inspect_object",
      "target_id": "wolf_tracks",
      "npc_id": "guard_001",
      "location": "north_road",
      "world_id": "default",
      "payload": {},
      "note": null
    }
  ],
  "action_results": [],
  "events": [],
  "executed_actions": [],
  "quest_updates": [],
  "player_state": {
    "player_id": "player_001",
    "name": "Gary",
    "location": "north_road",
    "inventory": ["old_sword", "bread"],
    "active_quests": ["investigate_wolves"],
    "completed_quests": [],
    "quest_progress": {},
    "world_flags": {
      "wolves_near_village": true,
      "mine_unlocked": false
    },
    "relationships": {
      "blacksmith_001": 0,
      "healer_001": 0,
      "guard_001": 0
    }
  }
}
```

Related endpoints:

- `POST /world/events`
- `GET /world/events`
- `POST /world/actions`

## Debug Traces

### `GET /debug/traces`

Lists recent prompt traces.

Query parameters:

- `limit`: optional, `1..100`, default `20`

Request:

```bash
curl "http://127.0.0.1:8000/debug/traces?limit=5"
```

Response:

```json
{
  "traces": [
    {
      "request_id": "9b3d1ef3-4020-4339-a8fe-1ef90a010101",
      "created_at": "2026-05-25T10:00:00Z",
      "agent_type": "chat",
      "npc_id": "blacksmith_001",
      "player_id": "player_001",
      "message_preview": "Any news about the wolves?",
      "estimated_prompt_tokens": 1200,
      "estimated_saved_tokens": 250,
      "actions_count": 1,
      "executed_actions_count": 1,
      "elapsed_ms": 230,
      "error": null
    }
  ]
}
```

Related endpoints:

- `GET /debug/traces/latest`
- `GET /debug/traces/{request_id}`

Error for trace lookup:

```json
{
  "error": {
    "code": "prompt_trace_not_found",
    "message": "Prompt trace not found: missing_request",
    "details": {
      "resource": "prompt_trace",
      "identifier": "missing_request"
    }
  }
}
```

