import json
from typing import List, Optional
from blade.units.Weapon import Weapon
from blade.utils.colors import convert_color_name_to_side_color, SIDE_COLOR


# 飞行记录黑匣子，用于记录飞机在每个时间步的位置和状态。
class BlackBox:
    def __init__(self):
        # 日志列表，每条日志包含时间戳、经纬度、航向、速度、燃料等信息
        self._logs = []

    # 在日志中添加一条记录，附带输入校验。
    def log(self, timestamp, latitude, longitude, heading, speed, fuel):
        if not isinstance(timestamp, (int, float)):
            raise ValueError("Timestamp must be a number.")
        if not (-90 <= latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90.")
        if not (-180 <= longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180.")
        if not isinstance(heading, (int, float)):
            raise ValueError("Heading must be a number.")
        if speed < 0:
            raise ValueError("Speed must be non-negative.")
        if fuel < 0:
            raise ValueError("Fuel must be non-negative.")

        self._logs.append(
            {
                "timestamp": timestamp,
                "latitude": latitude,
                "longitude": longitude,
                "heading": heading,
                "speed": speed,
                "fuel": fuel,
            }
        )

    # 根据时间戳获取日志，可指定只返回某个字段。
    def get_logs(self, timestamp=None, key: str = ""):
        if timestamp is None:
            return self._logs

        if not (0 <= timestamp < len(self._logs)):
            raise IndexError("Timestamp out of range.")

        log = self._logs[timestamp]

        if key:
            if key not in log:
                raise KeyError(f"Key '{key}' not found in log(s).")
            return log[key]

        return log

    # 以美化 JSON 格式返回最后一条日志。
    def get_last_log_pp(self):
        if not self._logs:
            return None

        import json

        formatted_log = json.dumps(self._logs[-1], indent=4, sort_keys=True)

        return formatted_log

    # 返回最后一条日志的原始字典。
    def get_last_log(self):
        if not self._logs:
            return None

        return self._logs[-1]

    # 根据键值对筛选日志。
    def filter_logs_by_key(self, key, value):
        if not self._logs:
            return []

        if key not in self._logs[0]:
            raise KeyError(f"Key '{key}' not found in log entries.")

        return [log for log in self._logs if log[key] == value]


# 飞机类，表示一架可以飞行、携带武器、执行任务的空中单位。
class Aircraft:

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
        route: Optional[List[List[float]]] = None,  # 航线，一组 [纬度, 经度] 坐标点
        selected: bool = False,
        side_color: str | SIDE_COLOR | None = None,
        weapons: Optional[List[Weapon]] = None,     # 携带的武器列表
        home_base_id: Optional[str] = "",           # 所属基地 ID
        rtb: bool = False,                          # 是否正在返回基地
        target_id: Optional[str] = "",              # 当前追击/攻击的目标 ID
        desired_route: Optional[List[List[float]]] = None,  # 期望航线（可能由 AI 生成）
    ):
        # 飞机唯一标识
        self.id = id
        # 飞机名称
        self.name = name
        # 所属阵营 ID
        self.side_id = side_id
        # 飞机型号，如 F-16C
        self.class_name = class_name
        # 当前纬度
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
        # 最大航程
        self.range = range
        # 航线点列表，默认为空
        self.route = route if route is not None else []
        # 是否被选中
        self.selected = selected
        # 飞机在地图上的显示颜色
        self.side_color = convert_color_name_to_side_color(side_color)
        # 携带的武器列表，默认为空
        self.weapons = weapons if weapons is not None else []
        # 所属基地 ID，默认为空
        self.home_base_id = home_base_id if home_base_id is not None else ""
        # 是否正在返回基地
        self.rtb = rtb
        # 当前攻击目标 ID，默认为空（不追击任何目标）
        self.target_id = target_id if target_id is not None else ""
        # 飞行黑匣子，记录飞行轨迹
        self.black_box = BlackBox()
        # 期望航线，默认为空
        self.desired_route = desired_route if desired_route is not None else []

    # 计算飞机携带的所有武器的总数量。
    def get_total_weapon_quantity(self) -> int:
        return sum([weapon.current_quantity for weapon in self.weapons])

    # 获取武器中交战距离最大的武器。
    def get_weapon_with_highest_engagement_range(self) -> Weapon | None:
        if len(self.weapons) == 0:
            return None
        return max(self.weapons, key=lambda weapon: weapon.get_engagement_range())

    # 返回飞机的探测距离（此处直接使用航程 range）。
    def get_detection_range(self) -> float:
        return self.range

    # 根据武器 ID 获取飞机携带的某个武器。
    def get_weapon(self, weapon_id: str) -> Weapon | None:
        for weapon in self.weapons:
            if weapon.id == weapon_id:
                return weapon
        return None

    # 将飞机信息导出为字典，方便序列化。
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
            "home_base_id": str(self.home_base_id),
            "rtb": self.rtb,
            "target_id": str(self.target_id),
        }
