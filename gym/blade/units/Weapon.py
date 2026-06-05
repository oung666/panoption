import json
from typing import List, Optional
from blade.utils.colors import convert_color_name_to_side_color, SIDE_COLOR


# 武器类，表示一种可发射的弹药类型，既可作为库存模板，也可作为已发射的飞行实体。
class Weapon:
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
        ] = None,  # 飞行路线，一组 [纬度, 经度] 坐标点
        side_color: str | SIDE_COLOR | None = None,
        target_id: Optional[str] = None,   # 攻击目标 ID（已发射后才有）
        lethality: float = 0.0,            # 杀伤概率（0-1 之间）
        max_quantity: int = 0,             # 最大库存数量
        current_quantity: int = 0,         # 当前库存数量（发射后递减）
    ):
        # 武器唯一标识
        self.id = id
        # 武器名称
        self.name = name
        # 所属阵营 ID
        self.side_id = side_id
        # 武器型号/类别名称
        self.class_name = class_name
        # 当前纬度（库存时为发射平台位置）
        self.latitude = latitude
        # 当前经度
        self.longitude = longitude
        # 当前高度
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
        # 最大射程
        self.range = range
        # 攻击目标 ID，库存武器为 None，发射后才分配目标
        self.target_id = target_id
        # 单发杀伤概率（0 到 1）
        self.lethality = lethality
        # 最大库存数量
        self.max_quantity = max_quantity
        # 当前库存数量
        self.current_quantity = current_quantity
        # 飞行路线点列表，默认为空
        self.route = route if route is not None else []
        # 武器在地图上的显示颜色
        self.side_color = convert_color_name_to_side_color(side_color)

    # 计算武器交战距离：速度 × 可飞行时间（当前燃料 / 燃料消耗率）。
    def  get_engagement_range(self) -> float:
        return self.speed * (self.current_fuel / self.fuel_rate)

    # 将武器信息导出为字典，方便序列化。
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
            "target_id": str(self.target_id),
            "lethality": self.lethality,
            "max_quantity": self.max_quantity,
            "current_quantity": self.current_quantity,
            "route": self.route,
            "side_color": (
                self.side_color.value
                if isinstance(self.side_color, SIDE_COLOR)
                else self.side_color
            ),
        }
