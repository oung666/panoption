from blade.units.Aircraft import Aircraft
from blade.units.Ship import Ship
from blade.units.Facility import Facility
from blade.units.Airbase import Airbase
from blade.units.Weapon import Weapon
from blade.Scenario import Scenario
from shapely.geometry import Point
from uuid import uuid4

from blade.utils.constants import NAUTICAL_MILES_TO_METERS
from blade.utils.utils import (
    get_bearing_between_two_points, #计算两个点之间的方位角。
    get_distance_between_two_points, #计算两个点之间的距离。
    get_next_coordinates,#根据当前位置、目标位置和移动距离计算下一步的坐标。
    get_terminal_coordinates_from_distance_and_bearing, #根据起始坐标、距离和方位角计算终点坐标。
    random_float,#生成指定范围内的随机浮点数。
    random_int,#生成指定范围内的随机整数。
)

# 目标可以是飞机、设施、武器、机场或舰船。
Target = Aircraft | Facility | Weapon | Airbase | Ship


# 判断威胁目标是否进入探测方的探测范围。
def is_threat_detected(
    threat: Aircraft | Weapon, detector: Facility | Ship | Aircraft
) -> bool:
    # 以探测方当前位置为圆心，根据探测距离构造一个近似探测区域。
    detector_geometry = Point([detector.latitude, detector.longitude]).buffer(
        detector.get_detection_range()
        / 60  # rough conversion from nautical miles to degrees
    )
    # 将威胁目标的位置表示为几何点。
    threat_geometry = Point([threat.latitude, threat.longitude])
    # 如果威胁目标位于探测区域内，则认为被探测到。
    return detector_geometry.contains(threat_geometry)


# 判断武器当前是否处于可攻击目标的距离范围内。
def weapon_can_engage_target(target: Target, weapon: Weapon) -> bool:
    # 获取武器的最大交战距离，单位为海里。
    weapon_engagement_range_nm = weapon.get_engagement_range()

    # 计算武器与目标之间的距离，返回单位为公里。
    distance_to_target_km = get_distance_between_two_points(
        weapon.latitude, weapon.longitude, target.latitude, target.longitude
    )

    # 将距离从公里转换为海里。
    distance_to_target_nm = (distance_to_target_km * 1000) / NAUTICAL_MILES_TO_METERS

    # 目标距离小于武器交战距离时，说明可以攻击。
    return distance_to_target_nm < weapon_engagement_range_nm


# 统计当前有多少枚武器正在追踪同一个目标。
def check_target_tracked_by_count(current_scenario: Scenario, target: Target) -> int:
    count = 0
    for weapon in current_scenario.weapons:
        # 武器记录的目标 ID 与当前目标 ID 一致，说明该武器正在追踪该目标。
        if weapon.target_id == target.id:
            count += 1
    return count


# 武器进入终端阶段后，进行命中概率判定并处理目标毁伤。
def weapon_endgame(current_scenario: Scenario, weapon: Weapon, target: Target) -> bool:
    # 武器进入终端阶段后，无论是否命中，都从场景中移除。
    current_scenario.weapons.remove(weapon)
    # 根据武器杀伤概率判断是否命中目标。
    if random_float(0, 1) <= weapon.lethality:
        # 根据目标类型，将被摧毁的目标从对应列表中移除。
        if isinstance(target, Aircraft):
            current_scenario.aircraft.remove(target)
        elif isinstance(target, Ship):
            current_scenario.ships.remove(target)
        elif isinstance(target, Facility):
            current_scenario.facilities.remove(target)
        elif isinstance(target, Airbase):
            current_scenario.airbases.remove(target)
        elif isinstance(target, Weapon):
            current_scenario.weapons.remove(target)
        return True
    return False




# 从飞机、舰船或设施平台向指定目标发射武器。
def launch_weapon(
    current_scenario: Scenario,
    origin: Facility | Ship | Aircraft,
    target: Target,
    launched_weapon: Weapon,
    launched_weapon_quantity: int,
) -> None:
    # 如果发射平台没有武器，或库存数量不足，则不执行发射。
    if (
        len(origin.weapons) == 0
        or launched_weapon.current_quantity < launched_weapon_quantity
    ):
        return

    # 按指定数量逐枚生成已经发射出去的武器实体。
    for _ in range(launched_weapon_quantity):
        # 计算武器发射后朝目标方向移动一步的位置。
        next_weapon_coordinates = get_next_coordinates(
            origin.latitude,
            origin.longitude,
            target.latitude,
            target.longitude,
            launched_weapon.speed,
        )
        next_weapon_latitude = next_weapon_coordinates[0]
        next_weapon_longitude = next_weapon_coordinates[1]
        # 创建一枚新的武器对象，表示已经离开发射平台并进入场景的武器。
        new_weapon = Weapon(
            id=str(uuid4()),
            name=f"{launched_weapon.name} #{random_int(0, 1000)}",
            side_id=origin.side_id,
            class_name=launched_weapon.class_name,
            latitude=next_weapon_latitude,
            longitude=next_weapon_longitude,
            altitude=launched_weapon.altitude,
            heading=get_bearing_between_two_points(
                next_weapon_latitude,
                next_weapon_longitude,
                target.latitude,
                target.longitude,
            ),
            speed=launched_weapon.speed,
            current_fuel=launched_weapon.current_fuel,
            max_fuel=launched_weapon.max_fuel,
            fuel_rate=launched_weapon.fuel_rate,
            range=launched_weapon.range,
            route=[[target.latitude, target.longitude]],
            side_color=launched_weapon.side_color,
            target_id=target.id,
            lethality=launched_weapon.lethality,
            current_quantity=1,
            max_quantity=1,
        )
        # 将新发射的武器加入当前场景，后续仿真会继续更新它的位置。
        current_scenario.weapons.append(new_weapon)
    # 从发射平台库存中扣除已发射的武器数量。
    launched_weapon.current_quantity -= launched_weapon_quantity
    if launched_weapon.current_quantity < 1:
        # 如果库存耗尽，则从发射平台的武器列表中移除该武器条目。
        origin.weapons.remove(launched_weapon)


# 更新已经发射的武器，使其继续追踪目标、消耗燃料，并在接近目标时进入命中判定。
def weapon_engagement(current_scenario: Scenario, weapon: Weapon) -> None:
    # 根据武器记录的目标 ID 查找目标对象。
    target = current_scenario.get_target(weapon.target_id)
    if target is None:
        # 如果目标不存在，说明目标已被摧毁或丢失，武器失效并被移除。
        current_scenario.weapons.remove(weapon)
    else:
        weapon_route = weapon.route
        if len(weapon_route) > 0:
            # there is a weird bug where a weapon will be teleported a vast distance if it gets too close to the target but weaponEndgame is not called, current solution is to set threshold to 1 km
            # 当武器距离目标小于 1 公里时，进入终端命中判定阶段。
            if (
                get_distance_between_two_points(
                    weapon.latitude,
                    weapon.longitude,
                    target.latitude,
                    target.longitude,
                )
                < 1
            ):
                weapon_endgame(current_scenario, weapon, target)
            else:
                # 如果尚未进入终端阶段，则继续沿目标方向移动。
                next_weapon_coordinates = get_next_coordinates(
                    weapon.latitude,
                    weapon.longitude,
                    target.latitude,
                    target.longitude,
                    weapon.speed,
                )
                next_weapon_latitude = next_weapon_coordinates[0]
                next_weapon_longitude = next_weapon_coordinates[1]
                # 更新武器朝向，使其继续指向目标。
                weapon.heading = get_bearing_between_two_points(
                    next_weapon_latitude,
                    next_weapon_longitude,
                    target.latitude,
                    target.longitude,
                )
                # 更新武器当前位置。
                weapon.latitude = next_weapon_latitude
                weapon.longitude = next_weapon_longitude
                # 按每秒步长消耗燃料。
                weapon.current_fuel -= weapon.fuel_rate / 3600
                if weapon.current_fuel <= 0:
                    # 燃料耗尽后，武器失效并从场景中移除。
                    current_scenario.weapons.remove(weapon)


# 让飞机追击目标飞机，并规划到目标后方一定距离的位置。
def aircraft_pursuit(
    current_scenario: Scenario,
    aircraft: Aircraft,
) -> None:
    # 根据飞机记录的目标 ID 查找目标飞机。
    target = current_scenario.get_aircraft(aircraft.target_id)
    if target is None:
        # 如果目标飞机不存在，则清空追击目标。
        aircraft.target_id = ""
        return
    if len(aircraft.weapons) < 1:
        # 没有武器时不执行追击逻辑。
        return

    # 设置追击位置为目标飞机后方 5 海里。
    TRAIL_DISTANCE_NM = 5
    trail_km = (TRAIL_DISTANCE_NM * NAUTICAL_MILES_TO_METERS) / 1000
    # 目标航向反方向即为其后方方向。
    behind_bearing = (target.heading + 180) % 360
    # 计算目标后方 5 海里的尾随点坐标。
    trail_position = get_terminal_coordinates_from_distance_and_bearing(
        target.latitude,
        target.longitude,
        trail_km,
        behind_bearing,
    )
    trail_latitude = trail_position[0]
    trail_longitude = trail_position[1]

    # 将飞机航线设置为飞向目标后方的尾随点。
    aircraft.route = [
        [trail_latitude, trail_longitude],
    ]
    # 更新飞机朝向，使其指向尾随点。
    aircraft.heading = get_bearing_between_two_points(
        aircraft.latitude,
        aircraft.longitude,
        trail_latitude,
        trail_longitude,
    )


# 为飞机规划一个位于目标附近、满足攻击半径要求的打击位置。
def route_aircraft_to_strike_position(
    current_scenario: Scenario,
    aircraft: Aircraft,
    target_id: str,
    strike_radius_nm: float,
) -> None:
    # 根据目标 ID 获取目标对象。
    target = current_scenario.get_target(target_id)
    if target is None:
        return
    if len(aircraft.weapons) < 1:
        # 没有武器时不需要规划打击位置。
        return

    # 计算飞机指向目标的方位角。
    bearing_between_aircraft_and_target = get_bearing_between_two_points(
        aircraft.latitude, aircraft.longitude, target.latitude, target.longitude
    )
    # 计算目标指向飞机的方位角，用于在目标附近生成攻击位置。
    bearing_between_target_and_aircraft = get_bearing_between_two_points(
        target.latitude, target.longitude, aircraft.latitude, aircraft.longitude
    )
    # 从目标位置沿目标指向飞机的方向后退指定攻击半径，得到打击位置。
    strike_location = get_terminal_coordinates_from_distance_and_bearing(
        target.latitude,
        target.longitude,
        (strike_radius_nm * NAUTICAL_MILES_TO_METERS) / 1000,
        bearing_between_target_and_aircraft,
    )

    # 将打击位置加入飞机航线。
    aircraft.route.append([strike_location[0], strike_location[1]])
    # 使飞机机头朝向目标。
    aircraft.heading = bearing_between_aircraft_and_target
