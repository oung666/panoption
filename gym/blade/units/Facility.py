import json
from typing import List, Optional
from blade.units.Weapon import Weapon
from blade.utils.colors import convert_color_name_to_side_color, SIDE_COLOR


# 地面设施类，表示一个固定位置的地面单位（如雷达站、防空阵地等）。
class Facility:
    def __init__(
        self,
        id: str,
        name: str,
        side_id: str,
        class_name: str,
        latitude: float = 0.0,
        longitude: float = 0.0,
        altitude: float = 0.0,  # 海拔高度（英尺，海平面以上）
        range: float = 250.0,   # 探测/作用范围，默认 250 海里
        side_color: str | SIDE_COLOR | None = None,
        weapons: Optional[List[Weapon]] = None,  # 设施携带的武器列表
    ):
        # 设施唯一标识
        self.id = id
        # 设施名称
        self.name = name
        # 所属阵营 ID
        self.side_id = side_id
        # 设施类别名称
        self.class_name = class_name
        # 设施纬度
        self.latitude = latitude
        # 设施经度
        self.longitude = longitude
        # 设施海拔高度
        self.altitude = altitude
        # 设施探测/作用范围
        self.range = range
        # 设施在地图上的显示颜色
        self.side_color = convert_color_name_to_side_color(side_color)
        # 设施携带的武器，默认为空
        self.weapons = weapons if weapons is not None else []

    # 计算设施所有武器的总数量。
    def get_total_weapon_quantity(self) -> int:
        return sum([weapon.current_quantity for weapon in self.weapons])

    # 获取武器中交战距离最大的武器。
    def get_weapon_with_highest_engagement_range(self) -> Weapon | None:
        if len(self.weapons) == 0:
            return None
        return max(self.weapons, key=lambda weapon: weapon.get_engagement_range())

    # 返回设施的探测距离（此处直接使用 range）。
    def get_detection_range(self) -> float:
        return self.range

    # 将设施信息导出为字典，方便序列化。
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "side_id": str(self.side_id),
            "class_name": self.class_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "range": self.range,
            "side_color": (
                self.side_color.value
                if isinstance(self.side_color, SIDE_COLOR)
                else self.side_color
            ),
            "weapons": [weapon.to_dict() for weapon in self.weapons],
        }
