import re
import math
import random
from datetime import datetime
from typing import List
from blade.utils.constants import EARTH_RADIUS_KM, KILOMETERS_TO_NAUTICAL_MILES


# 将角度转换为弧度。
def to_radians(degrees: float) -> float:
    return math.radians(degrees)


# 将弧度转换为角度。
def to_degrees(radians: float) -> float:
    return math.degrees(radians)


# 计算两点之间的方位角（0-360 度），以北为 0°，顺时针增加。
def get_bearing_between_two_points(
    start_latitude: float,
    start_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> float:
    # 将输入的经纬度从角度转换为弧度
    start_latitude = to_radians(start_latitude)
    start_longitude = to_radians(start_longitude)
    destination_latitude = to_radians(destination_latitude)
    destination_longitude = to_radians(destination_longitude)

    # 使用球面三角公式计算方位角
    y = math.sin(destination_longitude - start_longitude) * math.cos(
        destination_latitude
    )
    x = math.cos(start_latitude) * math.sin(destination_latitude) - math.sin(
        start_latitude
    ) * math.cos(destination_latitude) * math.cos(
        destination_longitude - start_longitude
    )
    # atan2(y, x) 计算弧度方位角，转换为角度后归一化到 [0, 360)
    bearing = (to_degrees(math.atan2(y, x)) + 360) % 360

    return bearing


# 使用 Haversine 公式计算两点之间的地球大圆距离，返回单位为公里。
def get_distance_between_two_points(
    start_latitude: float,
    start_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> float:
    # 将经纬度转换为弧度
    φ1 = to_radians(start_latitude)
    φ2 = to_radians(destination_latitude)
    Δφ = to_radians(destination_latitude - start_latitude)
    Δλ = to_radians(destination_longitude - start_longitude)

    # Haversine 公式计算两点的球面距离
    a = math.sin(Δφ / 2) * math.sin(Δφ / 2) + math.cos(φ1) * math.cos(φ2) * math.sin(
        Δλ / 2
    ) * math.sin(Δλ / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    d = EARTH_RADIUS_KM * c  # 结果单位为公里

    return d


# 已知起点坐标、距离和方位角，计算终点的经纬度坐标。
def get_terminal_coordinates_from_distance_and_bearing(
    start_latitude: float, start_longitude: float, distance: float, bearing: float
) -> List[float]:
    # 方位角转换为弧度
    bearing_in_radians = to_radians(bearing)

    # 起点经纬度转换为弧度
    initial_latitude = to_radians(start_latitude)
    initial_longitude = to_radians(start_longitude)

    # 球面三角公式计算终点纬度
    final_latitude = math.asin(
        math.sin(initial_latitude) * math.cos(distance / EARTH_RADIUS_KM)
        + math.cos(initial_latitude)
        * math.sin(distance / EARTH_RADIUS_KM)
        * math.cos(bearing_in_radians)
    )
    # 球面三角公式计算终点经度
    final_longitude = initial_longitude + math.atan2(
        math.sin(bearing_in_radians)
        * math.sin(distance / EARTH_RADIUS_KM)
        * math.cos(initial_latitude),
        math.cos(distance / EARTH_RADIUS_KM)
        - math.sin(initial_latitude) * math.sin(final_latitude),
    )

    # 终点经纬度转换回角度
    final_latitude = to_degrees(final_latitude)
    final_longitude = to_degrees(final_longitude)

    return [final_latitude, final_longitude]


# 在指定范围内生成一个随机浮点数。
def random_float(min_value: float, max_value: float) -> float:
    return random.uniform(min_value, max_value)


# 在指定范围内生成一个随机整数。
def random_int(min_value: int, max_value: int) -> int:
    return random.randint(min_value, max_value)


# 根据平台速度和当前位置与目标位置，计算下一步应到达的坐标。
def get_next_coordinates(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
    platform_speed: float,
) -> List[float]:
    # 计算从当前位置到目标位置的方位角
    heading = get_bearing_between_two_points(
        origin_latitude, origin_longitude, destination_latitude, destination_longitude
    )
    # 计算起点到目标的总距离（公里）
    total_distance_km = get_distance_between_two_points(
        origin_latitude, origin_longitude, destination_latitude, destination_longitude
    )
    # 根据距离和速度计算总飞行时间（小时）
    total_time_hours = (total_distance_km * KILOMETERS_TO_NAUTICAL_MILES) / (
        platform_speed if platform_speed >= 0 else -platform_speed
    )
    # 总时间转换为秒（向下取整），防止除零错误
    total_time_seconds = max(
        math.floor(total_time_hours * 3600), 0.0001
    )
    # 每一步前进的距离（公里/秒 × 3600秒/小时的近似步长）
    leg_distance_km = total_distance_km / total_time_seconds

    # 如果剩余距离已经小于单步距离，直接返回目标位置
    if total_distance_km < leg_distance_km:
        return [destination_latitude, destination_longitude]

    # 否则沿着方位角方向移动单步距离，返回新坐标
    return get_terminal_coordinates_from_distance_and_bearing(
        origin_latitude, origin_longitude, leg_distance_km, heading
    )


# 将下划线命名转换为驼峰命名（camelCase）。
def to_camelcase(s):
    return re.sub(r"(?!^)_([a-zA-Z])", lambda m: m.group(1).upper(), s)


# 将 Unix 时间戳转换为本地时间字符串。
def unix_to_local_time(unix_timestamp: int, separator: str = ":") -> str:
    date = datetime.fromtimestamp(unix_timestamp)
    formatted_time = date.strftime(f"%H{separator}%M{separator}%S")
    return formatted_time
