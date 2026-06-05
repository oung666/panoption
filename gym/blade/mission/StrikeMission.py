import json
from typing import List


# 打击任务类，把作战单位分配给特定目标，定义一次主动攻击行动。
class StrikeMission:
    def __init__(
        self,
        id: str,
        name: str,
        side_id: str,
        assigned_unit_ids: List[str],   # 执行打击任务的单位 ID 列表（飞机、舰船等）
        assigned_target_ids: List[str], # 要打击的目标 ID 列表（敌机、敌舰、设施等）
        active: bool,                    # 任务是否激活
    ):
        # 任务唯一标识
        self.id = id
        # 任务名称
        self.name = name
        # 所属阵营 ID
        self.side_id = side_id
        # 执行此打击任务的单位 ID 列表
        self.assigned_unit_ids = assigned_unit_ids
        # 此任务要打击的目标 ID 列表
        self.assigned_target_ids = assigned_target_ids
        # 任务是否激活
        self.active = active

    # 将打击任务信息导出为字典，方便序列化。
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "side_id": str(self.side_id),
            "assigned_unit_ids": [str(id) for id in self.assigned_unit_ids],
            "assigned_target_ids": [str(id) for id in self.assigned_target_ids],
            "active": self.active,
        }
