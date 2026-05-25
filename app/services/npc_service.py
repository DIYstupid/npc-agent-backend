from app.data.seed import NPCS
from app.schemas.npc import NPCProfile


class NPCService:
    """
    NPC 服务。

    内部把 NPC list 转成 dict，方便通过 npc_id 快速查询。
    """

    def __init__(self) -> None:
        self.npcs: dict[str, NPCProfile] = {
            npc.npc_id: npc
            for npc in NPCS
        }

    def list_npcs(self) -> list[NPCProfile]:
        return list(self.npcs.values())

    def get_npc(self, npc_id: str) -> NPCProfile | None:
        return self.npcs.get(npc_id)
