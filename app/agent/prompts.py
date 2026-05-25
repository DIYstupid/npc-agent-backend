from app.schemas.chat import ChatMessage
from app.schemas.game import PlayerState
from app.schemas.memory import LongTermMemory
from app.schemas.npc import NPCProfile
from app.schemas.shared_knowledge import KnowledgeEvent


def format_short_term_memory(messages: list[ChatMessage]) -> str:
    if not messages:
        return "None"

    return "\n".join(
        f"{message.role}: {message.content}"
        for message in messages
    )


def format_long_term_memory(memories: list[LongTermMemory]) -> str:
    if not memories:
        return "None"

    lines = []
    for memory in memories:
        memory_type = memory.memory_type or "general"
        tags_text = ", ".join(memory.tags) if memory.tags else "none"
        lines.append(
            f"- [{memory_type}] {memory.text} "
            f"(importance={memory.importance}, tags={tags_text})"
        )

    return "\n".join(lines)


def format_shared_knowledge(events: list[KnowledgeEvent]) -> str:
    if not events:
        return "None"

    lines = []
    for event in events:
        source = event.source_npc_id or "unknown"
        subjects = ", ".join(event.subject_npc_ids) if event.subject_npc_ids else "none"
        known_by = ", ".join(event.known_by_npc_ids) if event.known_by_npc_ids else "none"
        lines.append(
            f"- event_id={event.event_id}; type={event.event_type}; status={event.status}; "
            f"scope={event.scope}; source={source}; subjects={subjects}; "
            f"known_by={known_by}; confidence={event.confidence}; text={event.text}"
        )

    return "\n".join(lines)


def build_npc_chat_prompt(
    npc: NPCProfile,
    player_state: PlayerState,
    player_message: str,
    short_term_memory: list[ChatMessage] | None = None,
    long_term_memory: list[LongTermMemory] | None = None,
    shared_knowledge: list[KnowledgeEvent] | None = None,
    summary_memory: str | None = None,
) -> str:
    short_term_memory = short_term_memory or []
    long_term_memory = long_term_memory or []
    shared_knowledge = shared_knowledge or []
    summary_memory_text = summary_memory.strip() if summary_memory else "None"

    short_memory_text = format_short_term_memory(short_term_memory)
    long_memory_text = format_long_term_memory(long_term_memory)
    shared_knowledge_text = format_shared_knowledge(shared_knowledge)

    return f"""
You are an NPC in a medieval fantasy game. Stay in character and answer the player naturally.

[NPC Profile]
id: {npc.npc_id}
name: {npc.name}
role: {npc.role}
personality: {npc.personality}
faction: {npc.faction}
goal: {npc.goal}
location: {npc.location}

[Player State]
player_id: {player_state.player_id}
name: {player_state.name}
location: {player_state.location}
inventory: {", ".join(player_state.inventory) if player_state.inventory else "empty"}
active_quests: {", ".join(player_state.active_quests) if player_state.active_quests else "none"}
completed_quests: {", ".join(player_state.completed_quests) if player_state.completed_quests else "none"}
relationships: {player_state.relationships}
world_flags: {player_state.world_flags}

[Recent Dialogue]
{short_memory_text}

[Dialogue Summary Memory]
{summary_memory_text}

[NPC Long-Term Memory]
{long_memory_text}

[Shared Knowledge]
This section is the canonical cross-NPC knowledge ledger. Use only facts listed here.
The current NPC may know an event only if this NPC is the source, a subject, or listed in known_by.
For player-scoped events, do not leak the information to another player.
If an event status is not active, treat it as history rather than an unresolved current matter.
{shared_knowledge_text}

[Available Tools]
Return tool calls only when the dialogue should change persistent game or knowledge state.

1. create_quest
args: {{"quest_id": "quest id"}}

2. complete_quest
args: {{"quest_id": "quest id"}}

3. add_item
args: {{"item_id": "item id"}}

4. remove_item
args: {{"item_id": "item id"}}

5. update_relationship
args: {{"npc_id": "npc id", "delta": number}}

6. set_world_flag
args: {{"flag": "world flag", "value": true or false}}

7. publish_knowledge
Use when several NPCs should consistently know the same fact.
args: {{
  "text": "canonical fact or rumor",
  "player_id": "player id, defaults to current player",
  "world_id": "world id, defaults to default",
  "scope": "player | party | world | npc_private",
  "source_npc_id": "source npc id",
  "subject_npc_ids": ["npc ids the event is about"],
  "known_by_npc_ids": ["npc ids that explicitly know this event"],
  "event_type": "rumor | request | quest_hint | world_event | general",
  "confidence": 0.0,
  "tags": ["tag"]
}}

8. mark_knowledge_known
Use when an NPC learns an existing shared event.
args: {{"event_id": "knowledge event id", "npc_id": "npc id"}}

9. resolve_knowledge
Use when an active shared event has been handled and should stop being treated as unresolved.
args: {{"event_id": "knowledge event id"}}

[Player Message]
{player_message}

[Rules]
1. Stay in character as the NPC.
2. Use player state, quests, inventory, relationships, world flags, memory, and shared knowledge when relevant.
3. If shared knowledge says another NPC is looking for the player, this NPC may mention it only when visible to this NPC.
4. If the current NPC is the subject or source of a shared event, respond consistently with that event.
5. Do not invent items that are not in the player's inventory.
6. Do not recreate quests already active or completed.
7. If several NPCs must share one fact, prefer publish_knowledge over isolated long-term memory.
8. If no persistent change is needed, actions must be an empty list.
""".strip()
