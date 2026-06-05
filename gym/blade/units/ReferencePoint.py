import json
from typing import Optional
from blade.utils.colors import convert_color_name_to_side_color, SIDE_COLOR


# 参考点类，表示地图上的一个标记点，用于划定巡逻区域边界或导航点。
class ReferencePoint:
    def __init__(
        self,
        id: str,
        name: str,
        side_id: str,
        latitude: float,
        longitude: float,
        altitude: float,
        side_color: str | SIDE_COLOR | None = None,
    ):
        # 参考点唯一标识
        self.id = id
        # 参考点名称
        self.name = name
        # 所属阵营 ID
        self.side_id = side_id
        # 参考点纬度
        self.latitude = latitude
        # 参考点经度
        self.longitude = longitude
        # 参考点海拔高度
        self.altitude = altitude
        # 参考点在地图上的显示颜色
        self.side_color = convert_color_name_to_side_color(side_color)

    # 将参考点信息导出为字典，方便序列化。
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "side_id": str(self.side_id),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "side_color": (
                self.side_color.value
                if isinstance(self.side_color, SIDE_COLOR)
                else self.side_color
            ),
        }
