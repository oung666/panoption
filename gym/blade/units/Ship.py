import json
from typing import List, Optional
from blade.units.Aircraft import Aircraft
from blade.units.Weapon import Weapon
from blade.utils.colors import convert_color_name_to_side_color, SIDE_COLOR


# 舰船类，表示一艘可以移动、携带武器和飞机的海军单位。
class Ship:

    def __init__(
        self,
        id: str,
        name: str,
        side_id: str,
        class_name: str,
        latitude: float,
        longitude: float,
        altitude: float,
        heading: float,
        speed: float,
        current_fuel: float,
        max_fuel: float,
        fuel_rate: float,  # 燃料消耗率，单位 lbs/hr
        range: float,
        route: Optional[
            List[List[float]]
        ] = None,  # 航线，一组 [纬度, 经度] 坐标点
        selected: bool = False,
        side_color: str | SIDE_COLOR | None = None,
        weapons: Optional[List[Weapon]] = None,       # 舰载武器列表
        aircraft: Optional[List[Aircraft]] = None,    # 舰载飞机列表
        desired_route: Optional[List[List[float]]] = None,  # 期望航线（可能由 AI 生成）
    ):
        # 舰船唯一标识
        self.id = id
        # 舰船名称
        self.name = name
        # 所属阵营 ID
        self.side_id = side_id
        # 舰船型号/类别名称
        self.class_name = class_name
        # 当前纬度
        self.latitude = latitude
        # 当前经度
        self.longitude = longitude
        # 当前海拔高度
        self.altitude = altitude
        # 当前航向角（0-360 度）
        self.heading = heading
        # 当前速度
        self.speed = speed
        # 当前剩余燃料
        self.current_fuel = current_fuel
        # 最大燃料容量
        self.max_fuel = max_fuel
        # 燃料消耗率
        self.fuel_rate = fuel_rate
        # 最大航程
        self.range = range
        # 航线点列表，默认为空
        self.route = route if route is not None else []
        # 是否被选中
        self.selected = selected
        # 舰船在地图上的显示颜色
        self.side_color = convert_color_name_to_side_color(side_color)
        # 舰载武器列表，默认为空
        self.weapons = weapons if weapons is not None else []
        # 舰载飞机列表，默认为空
        self.aircraft = aircraft if aircraft is not None else []
        # 期望航线，默认为空
        self.desired_route = desired_route if desired_route is not None else []

    # 计算舰船所有武器的总数量。
    def get_total_weapon_quantity(self) -> int:
        return sum([weapon.current_quantity for weapon in self.weapons])

    # 获取武器中交战距离最大的武器。
    def get_weapon_with_highest_engagement_range(self) -> Weapon | None:
        if len(self.weapons) == 0:
            return None
        return max(self.weapons, key=lambda weapon: weapon.get_engagement_range())

    # 返回舰船的探测距离（此处直接使用航程 range）。
    def get_detection_range(self) -> float:
        return self.range

    # 根据武器 ID 获取舰船携带的某个武器。
    def get_weapon(self, weapon_id: str) -> Weapon | None:
        for weapon in self.weapons:
            if weapon.id == weapon_id:
                return weapon
        return None

    # 将舰船信息导出为字典，方便序列化。
    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "side_id": str(self.side_id),
            "class_name": self.class_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "heading": self.heading,
            "speed": self.speed,
            "current_fuel": self.current_fuel,
            "max_fuel": self.max_fuel,
            "fuel_rate": self.fuel_rate,
            "range": self.range,
            "route": self.route,
            "selected": self.selected,
            "side_color": (
                self.side_color.value
                if isinstance(self.side_color, SIDE_COLOR)
                else self.side_color
            ),
            "weapons": [weapon.to_dict() for weapon in self.weapons],
            "aircraft": [ac.to_dict() for ac in self.aircraft],
        }
