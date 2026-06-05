from typing import Dict, List, Optional


class Relationships:
    """阵营关系管理：维护各方之间的敌对与盟友关系。"""

    def __init__(
        self,
        hostiles: Optional[Dict[str, List[str]]] = None,
        allies: Optional[Dict[str, List[str]]] = None,
    ):
        """初始化关系对象。
        Args:
            hostiles: {阵营ID: [敌对阵营ID列表]}，默认为空
            allies: {阵营ID: [盟友阵营ID列表]}，默认为空
        """
        self.hostiles: Dict[str, List[str]] = hostiles if hostiles is not None else {}
        self.allies: Dict[str, List[str]] = allies if allies is not None else {}

    def add_hostile(self, side_id: str, hostile_id: str):
        """将 hostile_id 设为 side_id 的敌对阵营，同时移除盟友关系（互斥）。"""
        if side_id not in self.hostiles:
            self.hostiles[side_id] = []
        if hostile_id not in self.hostiles[side_id]:
            self.hostiles[side_id].append(hostile_id)
        self.remove_ally(side_id, hostile_id)

    def remove_hostile(self, side_id: str, hostile_id: str):
        """移除 side_id 与 hostile_id 之间的敌对关系。"""
        if side_id in self.hostiles:
            self.hostiles[side_id] = [
                id for id in self.hostiles[side_id] if id != hostile_id
            ]

    def add_ally(self, side_id: str, ally_id: str):
        """将 ally_id 设为 side_id 的盟友，同时移除敌对关系（互斥）。"""
        if side_id not in self.allies:
            self.allies[side_id] = []
        if ally_id not in self.allies[side_id]:
            self.allies[side_id].append(ally_id)
        self.remove_hostile(side_id, ally_id)

    def remove_ally(self, side_id: str, ally_id: str):
        """移除 side_id 与 ally_id 之间的盟友关系。"""
        if side_id in self.allies:
            self.allies[side_id] = [id for id in self.allies[side_id] if id != ally_id]

    def is_ally(self, side_id: str, ally_id: str) -> bool:
        """判断 ally_id 是否为 side_id 的盟友。"""
        return ally_id in self.allies.get(side_id, [])

    def is_hostile(self, side_id: str, hostile_id: str) -> bool:
        """判断 hostile_id 是否为 side_id 的敌对阵营。"""
        return hostile_id in self.hostiles.get(side_id, [])

    def get_allies(self, side_id: str) -> List[str]:
        """获取 side_id 的所有盟友 ID 列表。"""
        return self.allies.get(side_id, [])

    def get_hostiles(self, side_id: str) -> List[str]:
        """获取 side_id 的所有敌对阵营 ID 列表。"""
        return self.hostiles.get(side_id, [])

    def update_relationship(self, side_id: str, hostiles: List[str], allies: List[str]):
        """整体更新 side_id 的敌对和盟友关系（覆盖式）。"""
        self.hostiles[side_id] = hostiles
        self.allies[side_id] = allies

    def delete_side(self, side_id: str):
        """删除某个阵营：从所有其他阵营的关系列表中移除该 side_id，并删除其自身的关���记录。"""
        for key in self.hostiles:
            self.hostiles[key] = [id for id in self.hostiles[key] if id != side_id]
        for key in self.allies:
            self.allies[key] = [id for id in self.allies[key] if id != side_id]
        self.hostiles.pop(side_id, None)
        self.allies.pop(side_id, None)

    def to_dict(self):
        """将关系导出为字典格式，用于 JSON 序列化。"""
        return {
            "hostiles": self.hostiles,
            "allies": self.allies,
        }
