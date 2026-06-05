import json
from typing import List
from random import random
from shapely.geometry import Point, Polygon
from blade.units.ReferencePoint import ReferencePoint


# 巡逻任务类，定义一个巡逻区域、分配单位，并提供区域内坐标检查与随机生成功能。
class PatrolMission:

    def __init__(
        self,
        id: str,
        name: str,
        side_id: str,
        assigned_unit_ids: List[str],
        assigned_area: List[ReferencePoint],
        active: bool,
    ):
        # 任务唯一标识
        self.id = id
        # 任务名称
        self.name = name
        # 所属阵营 ID
        self.side_id = side_id
        # 被分配到此巡逻任务的单位 ID 列表（飞机、舰船等）
        self.assigned_unit_ids = assigned_unit_ids
        # 巡逻区域，由多个参考点围成（通常为 4 个点组成的矩形区域）
        self.assigned_area = assigned_area
        # 任务是否激活
        self.active = active
        # 根据参考点构建的 Shapely 多边形几何区域，用于后续的包含判断
        self.patrol_area_geometry = Polygon(
            [(point.longitude, point.latitude) for point in self.assigned_area]
        )

    # 当参考点发生变化时，重建多边形几何区域。
    def update_patrol_area_geometry(self):
        self.patrol_area_geometry = Polygon(
            [(point.longitude, point.latitude) for point in self.assigned_area]
        )

    # 检查给定坐标是否落在巡逻区域内。
    def check_if_coordinates_is_within_patrol_area(
        self, coordinates: List[float]
    ) -> bool:
        # 将 [纬度, 经度] 列表转换为 Shapely 的 Point 对象
        point = Point(coordinates)
        # 调用 Polygin.contains() 判断点是否在多边形内
        if self.patrol_area_geometry.contains(point):
            return True
        return False

    # 在巡逻区域内随机生成一个坐标点。
    def generate_random_coordinates_within_patrol_area(self) -> List[float]:
        # 在 assigned_area 定义的矩形区域内，按均匀分布生成随机经纬度
        # [0] 为左下角参考点，[1] 提供右侧经度边界，[2] 提供上方纬度边界
        random_coordinates = [
            random() * (self.assigned_area[2].latitude - self.assigned_area[0].latitude)
            + self.assigned_area[0].latitude,
            random()
            * (self.assigned_area[1].longitude - self.assigned_area[0].longitude)
            + self.assigned_area[0].longitude,
        ]
        return random_coordinates

    # 将巡逻任务信息导出为字典，方便序列化。
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "side_id": str(self.side_id),
            "assigned_unit_ids": [str(id) for id in self.assigned_unit_ids],
            "assigned_area": [point.to_dict() for point in self.assigned_area],
            "active": self.active,
        }
