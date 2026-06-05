import json
from typing import List, Optional
from blade.units.Aircraft import Aircraft
from blade.utils.colors import convert_color_name_to_side_color, SIDE_COLOR


# 空军基地类，表示一个可驻扎飞机的机场。
class Airbase:

    def __init__(
        self,
        id: str,
        name: str,
        side_id: str,
        class_name: str,
        latitude: float,
        longitude: float,
        altitude: float,
        side_color: str | SIDE_COLOR | None = None,
        aircraft: Optional[List[Aircraft]] = None,  # 驻扎在此基地的飞机列表
    ):
        # 基地唯一标识
        self.id = id
        # 基地名称
        self.name = name
        # 所属阵营 ID
        self.side_id = side_id
        # 基地型号/类别名称
        self.class_name = class_name
        # 基地纬度
        self.latitude = latitude
        # 基地经度
        self.longitude = longitude
        # 基地海拔高度（英尺，海平面以上）
        self.altitude = altitude
        # 基地在地图上的显示颜色
        self.side_color = convert_color_name_to_side_color(side_color)
        # 驻扎的飞机列表，默认为空
        self.aircraft = aircraft if aircraft is not None else []

    # 将空军基地信息导出为字典，方便序列化为 JSON。
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "side_id": str(self.side_id),
            "class_name": self.class_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "side_color": (
                self.side_color.value
                if isinstance(self.side_color, SIDE_COLOR)
                else self.side_color
            ),
            "aircraft": [ac.to_dict() for ac in self.aircraft],
        }
