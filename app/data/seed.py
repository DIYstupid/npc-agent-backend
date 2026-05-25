from app.schemas.npc import NPCProfile
from app.schemas.game import PlayerState, QuestObjective, QuestProgress


NPCS = [
    NPCProfile(
        npc_id="blacksmith_001",
        name="格伦",
        role="铁匠",
        personality="粗鲁但重情义",
        faction="village",
        goal="找回失踪的学徒，并修复村庄的武器",
        location="blacksmith_shop",
    ),
    NPCProfile(
        npc_id="healer_001",
        name="艾琳",
        role="药师",
        personality="温和、谨慎、富有同情心",
        faction="village",
        goal="治疗村民并寻找稀有草药",
        location="healer_hut",
    ),
    NPCProfile(
        npc_id="guard_001",
        name="罗恩",
        role="守卫队长",
        personality="严肃、负责、不轻易信任陌生人",
        faction="village_guard",
        goal="保护村庄免受狼群袭击",
        location="village_gate",
    ),
]


PLAYERS = [
    PlayerState(
        player_id="player_001",
        name="Gary",
        location="village_square",
        inventory=["old_sword", "bread"],
        active_quests=["investigate_wolves"],
        completed_quests=[],
        quest_progress={
            "investigate_wolves": QuestProgress(
                quest_id="investigate_wolves",
                objectives=[
                    QuestObjective(
                        objective_id="visit_north_road",
                        type="location_visited",
                        description="Go to the north road where wolves were seen.",
                        location="north_road",
                    ),
                    QuestObjective(
                        objective_id="inspect_wolf_tracks",
                        type="inspect_object",
                        description="Inspect the wolf tracks near the road.",
                        target_id="wolf_tracks",
                    ),
                    QuestObjective(
                        objective_id="report_to_guard",
                        type="talk_to_npc",
                        description="Report the findings to the guard captain.",
                        npc_id="guard_001",
                    ),
                ],
            )
        },
        world_flags={
            "wolves_near_village": True,
            "mine_unlocked": False,
        },
        relationships={
            "blacksmith_001": 0,
            "healer_001": 0,
            "guard_001": 0,
        },
    )
]
