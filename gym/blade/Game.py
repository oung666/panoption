import json
import copy
from uuid import uuid4
from typing import Tuple, Optional
from blade.units.Aircraft import Aircraft
from blade.units.Airbase import Airbase
from blade.units.Facility import Facility
from blade.units.Ship import Ship
from blade.units.Weapon import Weapon
from blade.units.ReferencePoint import ReferencePoint
from blade.mission.PatrolMission import PatrolMission
from blade.mission.StrikeMission import StrikeMission
from blade.Scenario import Scenario
from blade.Side import Side
from blade.Relationships import Relationships
from blade.Doctrine import DoctrineType

from blade.utils.constants import NAUTICAL_MILES_TO_METERS
from blade.utils.colors import SIDE_COLOR
from blade.utils.PlaybackRecorder import PlaybackRecorder
from blade.utils.utils import (
    get_bearing_between_two_points,
    get_next_coordinates,
    get_distance_between_two_points,
    to_camelcase,
)
from blade.engine.weaponEngagement import (
    aircraft_pursuit,
    is_threat_detected,
    check_target_tracked_by_count,
    launch_weapon,
    route_aircraft_to_strike_position,
    weapon_engagement,
    weapon_can_engage_target,
)


# 游戏主类，封装整个仿真循环：单位移动、自动交战、场景加载/导出、录制等。
class Game:

    def __init__(
        self,
        current_scenario: Scenario,
        record_every_seconds: Optional[int] = None,
        recording_export_path: Optional[str] = ".",
    ):
        # 当前运行的场景
        self.current_scenario = current_scenario
        # 初始场景的深拷贝，用于 reset 时恢复
        self.initial_scenario = current_scenario

        # 当前操作方 ID（交互式控制时的视角方）
        self.current_side_id = ""
        # 是否正在录制场景
        self.recording_scenario = False
        # 回放录制器
        self.recorder = PlaybackRecorder(record_every_seconds, recording_export_path)
        # 场景是否暂停
        self.scenario_paused = True
        # 当前攻击方 ID
        self.current_attacker_id = ""
        # 地图视图状态（中心点、缩放级别）
        self.map_view = {
            "defaultCenter": [0, 0],
            "currentCameraCenter": [0, 0],
            "defaultZoom": 0,
            "currentCameraZoom": 0,
        }

    # --------------------- 单位管理 ---------------------

    # 从场景中删除指定 ID 的飞机。
    def remove_aircraft(self, aircraft_id: str) -> None:
        self.current_scenario.aircraft.remove(
            self.current_scenario.get_aircraft(aircraft_id)
        )

    # 飞机降落到基地：将在返航状态的飞机从场景中移除，加入其所属基地的飞机列表。
    def land_aicraft(self, aircraft_id: str) -> None:
        aircraft = self.current_scenario.get_aircraft(aircraft_id)
        if aircraft is not None and aircraft.rtb: # 只有在返航状态的飞机才能降落
            homebase = self.current_scenario.get_aircraft_homebase(aircraft.id)
            if homebase is not None:
                # 创建新的飞机对象，位置设在基地附近，rtb 设为 False
                new_aircraft = Aircraft(
                    id=aircraft.id,
                    name=aircraft.name,
                    side_id=aircraft.side_id,
                    class_name=aircraft.class_name,
                    latitude=homebase.latitude - 0.5,
                    longitude=homebase.longitude - 0.5,
                    altitude=aircraft.altitude,
                    heading=90.0,
                    speed=aircraft.speed,
                    current_fuel=aircraft.current_fuel,
                    max_fuel=aircraft.max_fuel,
                    fuel_rate=aircraft.fuel_rate,
                    range=aircraft.range,
                    side_color=aircraft.side_color,
                    weapons=aircraft.weapons,
                    home_base_id=aircraft.home_base_id,
                    rtb=False,
                    target_id=aircraft.target_id,
                )
                homebase.aircraft.append(new_aircraft)
                self.remove_aircraft(aircraft.id)

    # --------------------- 参考点管理 ---------------------

    # 在地图上添加一个参考点。
    def add_reference_point(
        self, reference_point_name: str, latitude: float, longitude: float
    ) -> ReferencePoint:
        if not self.current_side_id:
            return None

        reference_point = ReferencePoint(
            id=str(uuid4()),
            name=reference_point_name,
            side_id=self.current_side_id,
            latitude=latitude,
            longitude=longitude,
            altitude=0,
            side_color=self.current_scenario.get_side_color(self.current_side_id),
        )
        self.current_scenario.reference_points.append(reference_point)
        return reference_point

    # 从场景中删除指定 ID 的参考点。
    def remove_reference_point(self, reference_point_id: str) -> None:
        self.current_scenario.reference_points.remove(
            self.current_scenario.get_reference_point(reference_point_id)
        )

    # --------------------- 飞机起降 ---------------------

    # 从舰船上弹射飞机：从舰船的飞机列表中取出第一架，加入场景中的飞机列表。
    def launch_aircraft_from_ship(self, ship_id: str) -> Aircraft | None:
        if not self.current_side_id:
            return None

        ship = self.current_scenario.get_ship(ship_id)
        if ship and len(ship.aircraft) > 0:
            aircraft = ship.aircraft.pop(0)
            if aircraft:
                self.current_scenario.aircraft.append(aircraft)
                return aircraft

    # 从空军基地起飞飞机：从基地的飞机列表中取出第一架，加入场景中的飞机列表。
    def launch_aircraft_from_airbase(self, airbase_id: str) -> Aircraft | None:
        if not self.current_side_id:
            return None

        airbase = self.current_scenario.get_airbase(airbase_id)
        if airbase and len(airbase.aircraft) > 0:
            aircraft = airbase.aircraft.pop(0)
            if aircraft:
                self.current_scenario.aircraft.append(aircraft)
                return aircraft

    # --------------------- 任务管理 ---------------------

    # 创建巡逻任务：需要至少 3 个参考点来定义巡逻区域。
    def create_patrol_mission(
        self,
        mission_name: str,
        assigned_units: list[str],
        assigned_area: list[ReferencePoint],
    ) -> None:
        if len(assigned_area) < 3: # 巡逻区域至少需要 3 个参考点来形成一个多边形
            return
        current_side_id = self.current_scenario.get_side(self.current_side_id).id # 获取当前操作方 ID
        mission = PatrolMission(# 创建巡逻任务对象，分配单位和巡逻区域BV 
            id=str(uuid4()),
            name=mission_name,
            side_id=current_side_id if current_side_id else self.current_side_id,
            assigned_unit_ids=assigned_units,
            assigned_area=assigned_area,
            active=True,
        )
        self.current_scenario.missions.append(mission)

    # 更新巡逻任务：可修改任务名称、分配单位和巡逻区域。
    def update_patrol_mission(
        self,
        mission_id: str,
        mission_name: str,
        assigned_units: list[str],
        assigned_area: list[ReferencePoint],
    ) -> None:
        patrol_mission = self.current_scenario.get_patrol_mission(mission_id)# 根据 ID 获取要更新的巡逻任务对象
        if patrol_mission:
            if mission_name and mission_name != "":
                patrol_mission.name = mission_name
            if assigned_units and len(assigned_units) > 0:
                patrol_mission.assigned_unit_ids = assigned_units
            if assigned_area and len(assigned_area) > 2:
                patrol_mission.assigned_area = assigned_area
                patrol_mission.update_patrol_area_geometry()# 更新巡逻区域的几何信息（如边界框、中心点等）

    # 创建打击任务：指定攻击方和目标。
    def create_strike_mission(
        self,
        mission_name: str,
        assigned_attackers: list[str],
        assigned_targets: list[str],
    ) -> None:
        current_side_id = self.current_scenario.get_side(self.current_side_id).id # 获取当前操作方 ID
        strike_mission = StrikeMission(
            id=str(uuid4()),
            name=mission_name,# 任务名称
            side_id=current_side_id if current_side_id else self.current_side_id,# 任务所属阵营默认为当前操作方所在阵营
            assigned_unit_ids=assigned_attackers,# 分配的攻击单位 ID 列表
            assigned_target_ids=assigned_targets,# 分配的目标 ID 列表
            active=True,# 任务默认设为激活状态
        )
        self.current_scenario.missions.append(strike_mission)

    # 更新打击任务。
    def update_strike_mission(
        self,
        mission_id: str,
        mission_name: str,
        assigned_attackers: list[str],
        assigned_targets: list[str],
    ) -> None:
        strike_mission = self.current_scenario.get_strike_mission(mission_id)# 根据 ID 获取要更新的打击任务对象
        if strike_mission:
            if mission_name and mission_name != "":
                strike_mission.name = mission_name
            if assigned_attackers and len(assigned_attackers) > 0:
                strike_mission.assigned_unit_ids = assigned_attackers
            if assigned_targets and len(assigned_targets) > 0:
                strike_mission.assigned_target_ids = assigned_targets

    # 删除指定 ID 的任务（使用列表推导式过滤掉该任务）。
    def delete_mission(self, mission_id: str) -> None:
        self.current_scenario.missions = [
            mission
            for mission in self.current_scenario.missions
            if mission.id != mission_id
        ]

    # --------------------- 单位移动控制 ---------------------

    # 给飞机设定新航线：将传入的坐标列表作为飞机的 route。
    def move_aircraft(self, aircraft_id: str, new_coordinates: list) -> Aircraft | None:
        aircraft = self.current_scenario.get_aircraft(aircraft_id)# 根据 ID 获取飞机对象
        if aircraft:
            aircraft.route = []
            for i in range(len(new_coordinates)):# 将传入的坐标列表逐个添加到飞机的 route 中
                new_latitude = new_coordinates[i][0]
                new_longitude = new_coordinates[i][1]
                aircraft.route.append([new_latitude, new_longitude])
            return aircraft# 返回更新后的飞机对象

    # 给舰船设定新航线。
    def move_ship(self, ship_id: str, new_coordinates: list) -> Ship | None:
        ship = self.current_scenario.get_ship(ship_id)
        if ship:
            ship.route = []
            for i in range(len(new_coordinates)):
                new_latitude = new_coordinates[i][0]
                new_longitude = new_coordinates[i][1]
                ship.route.append([new_latitude, new_longitude])
            return ship

    # --------------------- 攻击与防御 ---------------------

    # 处理飞机攻击指令：飞机使用指定武器攻击目标。
    def handle_aircraft_attack(
        self, aircraft_id: str, target_id: str, weapon_id: str, weapon_quantity: int
    ) -> None:
        if weapon_quantity <= 0:
            return
        target = self.current_scenario.get_target(target_id)
        aircraft = self.current_scenario.get_aircraft(aircraft_id)
        # 验证目标和飞机存在、且属于不同阵营、不是自己打自己
        if (
            target
            and aircraft
            and target.side_id != aircraft.side_id
            and target.id != aircraft.id
        ):
            weapon = aircraft.get_weapon(weapon_id)
            if weapon:
                launch_weapon(
                    self.current_scenario, aircraft, target, weapon, weapon_quantity
                )

    # 处理舰船攻击指令。
    def handle_ship_attack(
        self, ship_id: str, target_id: str, weapon_id: str, weapon_quantity: int
    ) -> None:
        if weapon_quantity <= 0:
            return
        target = self.current_scenario.get_target(target_id)
        ship = self.current_scenario.get_ship(ship_id)
        if target and ship and target.side_id != ship.side_id and target.id != ship.id:
            weapon = ship.get_weapon(weapon_id)
            if weapon:
                launch_weapon(
                    self.current_scenario, ship, target, weapon, weapon_quantity
                )

    # 飞机返航指令：切换 rtb 状态或将航线设为飞回基地。
    def aircraft_return_to_base(self, aircraft_id: str) -> Aircraft | None:
        aircraft = self.current_scenario.get_aircraft(aircraft_id)
        if aircraft:
            if aircraft.rtb:
                # 如果已经在返航中，则取消返航
                aircraft.rtb = False
                aircraft.route = []
                return aircraft
            else:
                # 启用返航，将航线设为飞回所属基地或最近的基地
                aircraft.rtb = True
                homebase = (
                    self.current_scenario.get_aircraft_homebase(aircraft.id)
                    if aircraft.home_base_id != ""
                    else self.current_scenario.get_closest_base_to_aircraft(aircraft.id)
                )
                if homebase:
                    if aircraft.home_base_id != homebase.id:
                        aircraft.home_base_id = homebase.id
                    return self.move_aircraft(
                        aircraft_id, [[homebase.latitude, homebase.longitude]]
                    )

    # 计算飞机返回基地所需的燃料量。
    def get_fuel_needed_to_return_to_base(self, aircraft: Aircraft) -> float:
        if aircraft.speed == 0:
            return 0
        if aircraft.home_base_id != "":# 如果飞机有指定基地，则使用该基地作为返航目标，否则使用最近的基地
            home_base = self.current_scenario.get_aircraft_homebase(aircraft.id)
        else:
            home_base = self.current_scenario.get_closest_base_to_aircraft(aircraft.id)

        if home_base:
            # 计算飞机到基地的距离（海里）
            distance_between_aircraft_and_base_nm = (
                get_distance_between_two_points(
                    aircraft.latitude,
                    aircraft.longitude,
                    home_base.latitude,
                    home_base.longitude,
                )
                * 1000
            ) / NAUTICAL_MILES_TO_METERS

            # 飞行时间 = 距离 / 速度
            time_needed_to_return_to_base_hr = (
                distance_between_aircraft_and_base_nm / aircraft.speed
            )
            # 所需燃料 = 飞行时间 × 燃料消耗率
            fuel_needed_to_return_to_base = (
                time_needed_to_return_to_base_hr * aircraft.fuel_rate
            )

            return fuel_needed_to_return_to_base

        return 0

    # --------------------- 自动防御逻辑 ---------------------

    # 设施自动防御：SAM（地空导弹）阵地自动攻击敌方飞机和来袭武器。
    def facility_auto_defense(self) -> None:
        for facility in self.current_scenario.facilities:
            # 检查该设施所在阵营是否启用 SAM 攻击条令
            if self.current_scenario.check_side_doctrine(
                facility.side_id, DoctrineType.SAM_ATTACK_HOSTILE
            ):
                # 对敌方飞机进行拦截
                for aircraft in self.current_scenario.aircraft:
                    if self.current_scenario.is_hostile(facility.side_id, aircraft.side_id):
                        facility_weapon = (
                            facility.get_weapon_with_highest_engagement_range()
                        )
                        if facility_weapon is None:
                            continue
                        # 三个条件：探测到、射程内、追踪该目标的武器少于 10 枚
                        if (
                            is_threat_detected(aircraft, facility)
                            and weapon_can_engage_target(aircraft, facility_weapon)
                            and check_target_tracked_by_count(
                                self.current_scenario, aircraft
                            )
                            < 10
                        ):
                            launch_weapon(
                                self.current_scenario,
                                facility,
                                aircraft,
                                facility_weapon,
                                1,
                            )
            # 拦截以设施为目标的敌方武器
            for weapon in self.current_scenario.weapons:
                if self.current_scenario.is_hostile(facility.side_id, weapon.side_id):
                    facility_weapon = (
                        facility.get_weapon_with_highest_engagement_range()
                    )
                    if facility_weapon is None:
                        continue
                    # 条件：武器目标是该设施、探测到、射程内、追踪武器少于 5 枚
                    if (
                        weapon.target_id == facility.id
                        and is_threat_detected(weapon, facility)
                        and weapon_can_engage_target(weapon, facility_weapon)
                        and check_target_tracked_by_count(self.current_scenario, weapon)
                        < 5
                    ):
                        launch_weapon(
                            self.current_scenario,
                            facility,
                            weapon,
                            facility_weapon,
                            1,
                        )

    # 舰船自动防御：舰船自动攻击敌方飞机和来袭武器。
    def ship_auto_defense(self) -> None:
        for ship in self.current_scenario.ships:
            # 检查该舰船所在阵营是否启用舰船攻击条令
            if self.current_scenario.check_side_doctrine(
                ship.side_id, DoctrineType.SHIP_ATTACK_HOSTILE
            ):
                # 对敌方飞机进行拦截
                for aircraft in self.current_scenario.aircraft:
                    if self.current_scenario.is_hostile(ship.side_id, aircraft.side_id):
                        ship_weapon = ship.get_weapon_with_highest_engagement_range()
                        if ship_weapon is None:
                            continue
                        if (
                            is_threat_detected(aircraft, ship)
                            and weapon_can_engage_target(aircraft, ship_weapon)
                            and check_target_tracked_by_count(
                                self.current_scenario, aircraft
                            )
                            < 10
                        ):
                            launch_weapon(
                                self.current_scenario,
                                ship,
                                aircraft,
                                ship_weapon,
                                1,
                            )
            # 拦截以舰船为目标的敌方武器
            for weapon in self.current_scenario.weapons:
                if self.current_scenario.is_hostile(ship.side_id, weapon.side_id):
                    ship_weapon = ship.get_weapon_with_highest_engagement_range()
                    if ship_weapon is None:
                        continue
                    if (
                        weapon.target_id == ship.id
                        and is_threat_detected(weapon, ship)
                        and weapon_can_engage_target(weapon, ship_weapon)
                        and check_target_tracked_by_count(self.current_scenario, weapon)
                        < 5
                    ):
                        launch_weapon(
                            self.current_scenario,
                            ship,
                            weapon,
                            ship_weapon,
                            1,
                        )

    # 飞机空对空自动交战：飞机自动攻击探测范围内的敌方飞机和武器。遍历无人机和场景内的武器和飞机，检查是否满足攻击条件（敌对、探测到、射程内、追踪数量少于阈值），满足则发起攻击。
    def aircraft_air_to_air_engagement(self) -> None:
        for aircraft in self.current_scenario.aircraft:
            # 没有武器则跳过
            if len(aircraft.weapons) == 0:
                continue
            aircraft_weapon_with_max_range = (
                aircraft.get_weapon_with_highest_engagement_range()
            )
            if aircraft_weapon_with_max_range is None:
                continue
            # 检查是否启用飞机攻击条令
            if self.current_scenario.check_side_doctrine(
                aircraft.side_id, DoctrineType.AIRCRAFT_ATTACK_HOSTILE
            ):
                # 攻击敌方飞机
                for enemy_aircraft in self.current_scenario.aircraft:
                    if self.current_scenario.is_hostile(# 检查是否为敌方飞机
                        aircraft.side_id, enemy_aircraft.side_id
                    ) and (# 目标飞机没有被当前飞机锁定，或已经被锁定但不是这架敌机，避免重复攻击同一目标
                        aircraft.target_id == "" or aircraft.target_id == enemy_aircraft.id
                    ):
                        if (# 满足攻击条件：探测到、射程内、追踪该目标的武器少于 1 枚
                            is_threat_detected(enemy_aircraft, aircraft)
                            and weapon_can_engage_target(
                                enemy_aircraft, aircraft_weapon_with_max_range
                            )
                            and check_target_tracked_by_count(
                                self.current_scenario, enemy_aircraft
                            )
                            < 1
                        ):# 发起攻击，发射一枚武器
                            launch_weapon(
                                self.current_scenario,
                                aircraft,
                                enemy_aircraft,
                                aircraft_weapon_with_max_range,
                                1,
                            )
                            aircraft.target_id = enemy_aircraft.id
            # 攻击以本机为目标的敌方武器
            for enemy_weapon in self.current_scenario.weapons:
                if self.current_scenario.is_hostile(
                    aircraft.side_id, enemy_weapon.side_id
                ):
                    if (# 满足攻击条件：武器目标是当前飞机、探测到、射程内、追踪该目标的武器少于 1 枚
                        enemy_weapon.target_id == aircraft.id
                        and is_threat_detected(enemy_weapon, aircraft)
                        and weapon_can_engage_target(
                            enemy_weapon, aircraft_weapon_with_max_range
                        )
                        and check_target_tracked_by_count(
                            self.current_scenario, enemy_weapon
                        )
                        < 1
                    ):
                        launch_weapon(
                            self.current_scenario,
                            aircraft,
                            enemy_weapon,
                            aircraft_weapon_with_max_range,
                            1,
                        )
            # 如果启用了追击条令且飞机有当前目标，执行追击逻辑
            if self.current_scenario.check_side_doctrine(
                aircraft.side_id, DoctrineType.AIRCRAFT_CHASE_HOSTILE
            ) and aircraft.target_id and aircraft.target_id != "":
                aircraft_pursuit(self.current_scenario, aircraft)

    # --------------------- 任务更新逻辑 ---------------------

    # 更新巡逻任务中的单位：如果单位没有航线，则在巡逻区域内随机生成一个航点；
    # 如果航点不在巡逻区域，则重新生成。
    def update_units_on_patrol_mission(self):
        active_patrol_missions = list(
            filter(
                lambda mission: mission.active,
                self.current_scenario.get_all_patrol_missions(),
            )
        )
        if len(active_patrol_missions) < 1:
            return
        # 遍历所有激活的巡逻任务，检查分配的单位和巡逻区域是否合理，
        # 并为没有航线或航线不在区域内的单位生成新的航点
        for mission in active_patrol_missions:
            if len(mission.assigned_area) < 3:
                continue
            # 遍历任务分配的单位 ID 列表，获取对应的飞机对象，检查航线并生成新的航点
            for unit_id in mission.assigned_unit_ids:
                unit = self.current_scenario.get_aircraft(unit_id)
                if unit is None:
                    continue
                # 如果单位没有航线，在巡逻区内随机生成一个航点
                if len(unit.route) == 0:
                    random_waypoint_in_patrol_area = (
                        mission.generate_random_coordinates_within_patrol_area()
                    )
                    unit.route.append(random_waypoint_in_patrol_area)
                elif len(unit.route) > 0:
                    # 如果当前航点不在巡逻区域内，则重新生成
                    if not mission.check_if_coordinates_is_within_patrol_area(
                        [unit.route[0][1], unit.route[0][0]]
                    ):
                        unit.route = []
                        random_waypoint_in_patrol_area = (
                            mission.generate_random_coordinates_within_patrol_area()
                        )
                        unit.route.append(random_waypoint_in_patrol_area)

    # 清理已完成的打击任务：目标不存在、攻击方弹药耗尽或全部损失时，
    # 任务结束并根据条令触发返航。
    def clear_completed_strike_missions(self) -> None:
        def mission_filter(mission):
            # 检查是否为打击任务
            if isinstance(mission, StrikeMission):
                # 初始化任务状态为进行中
                is_mission_ongoing = True

                # 获取打击任务的目标
                target = self.current_scenario.get_target(
                    mission.assigned_target_ids[0]
                )

                # 目标不存在 → 任务完成
                if not target:
                    is_mission_ongoing = False

                # 获取还存活的攻击方
                attackers = list(
                    filter(
                        lambda attacker: attacker is not None,
                        [
                            self.current_scenario.get_aircraft(attacker_id)
                            for attacker_id in mission.assigned_unit_ids
                        ],
                    )
                )

                # 攻击方全部损失 → 任务失败
                if len(attackers) < 1:
                    is_mission_ongoing = False

                # 攻击方弹药全部耗尽 → 任务完成
                all_attackers_expended = all(
                    attacker.get_total_weapon_quantity() == 0 for attacker in attackers
                )

                if all_attackers_expended:
                    is_mission_ongoing = False

                # 如果任务不继续且启用了"完成任务后返航"条令，让攻击方返航
                if self.current_scenario.check_side_doctrine(
                    mission.side_id, DoctrineType.AIRCRAFT_RTB_WHEN_STRIKE_MISSION_COMPLETE
                ) and not is_mission_ongoing:
                    for attacker in attackers:
                        self.aircraft_return_to_base(attacker.id)

                return is_mission_ongoing
            else:
                # 非打击任务（巡逻任务），保留
                return True

        # 只保留仍在进行中的任务
        self.current_scenario.missions = list(
            filter(mission_filter, self.current_scenario.missions)
        )

    # 更新打击任务中的单位：让攻击方飞到攻击位置，满足条件时发射武器。
    def update_units_on_strike_mission(self):
        # 获取所有激活的打击任务，如果没有则返回
        active_strike_missions = list(
            filter(
                lambda mission: mission.active,
                self.current_scenario.get_all_strike_missions(),
            )
        )
        if len(active_strike_missions) < 1:
            return

        for mission in active_strike_missions:
            # 如果没有分配目标，则跳过该任务
            if len(mission.assigned_target_ids) < 1:
                continue
            # 获取打击任务的目标
            for attacker_id in mission.assigned_unit_ids:
                attacker = self.current_scenario.get_aircraft(attacker_id)
                if attacker is None:
                    continue
                target = self.current_scenario.get_target(
                    mission.assigned_target_ids[0]
                )
                if target is None:
                    continue

                # 计算攻击位置（航线终点）到目标的距离（海里）
                distance_between_weapon_launch_position_and_target_nm = None
                if len(attacker.route) > 0:
                    distance_between_weapon_launch_position_and_target_nm = (
                        get_distance_between_two_points(
                            attacker.route[len(attacker.route) - 1][0],
                            attacker.route[len(attacker.route) - 1][1],
                            target.latitude,
                            target.longitude,
                        )
                        * 1000
                    ) / NAUTICAL_MILES_TO_METERS

                # 计算攻击方当前到目标的距离（海里）
                distance_between_attacker_and_target_nm = (
                    get_distance_between_two_points(
                        attacker.latitude,
                        attacker.longitude,
                        target.latitude,
                        target.longitude,
                    )
                    * 1000
                ) / NAUTICAL_MILES_TO_METERS
                # 获取攻击方携带的武器中射程最远的武器
                aircraft_weapon_with_max_range = (
                    attacker.get_weapon_with_highest_engagement_range()
                )
                if aircraft_weapon_with_max_range is None:
                    continue

                # 如果攻击位置超出探测范围或武器射程（含 10% 余量），则重新规划攻击航线
                if (
                    distance_between_weapon_launch_position_and_target_nm is not None
                    and (
                        distance_between_weapon_launch_position_and_target_nm
                        > attacker.get_detection_range() * 1.1
                        or distance_between_weapon_launch_position_and_target_nm
                        > aircraft_weapon_with_max_range.get_engagement_range() * 1.1
                    )
                ) or (
                    distance_between_weapon_launch_position_and_target_nm is None
                    and (
                        distance_between_attacker_and_target_nm
                        > attacker.get_detection_range() * 1.1
                        or distance_between_attacker_and_target_nm
                        > aircraft_weapon_with_max_range.get_engagement_range() * 1.1
                    )
                ):
                    #攻击半径取探测范围和武器射程的较小值。让飞机飞到距离目标这个半径的攻击位置。
                    route_aircraft_to_strike_position(
                        self.current_scenario,
                        attacker,
                        mission.assigned_target_ids[0],
                        min(
                            attacker.get_detection_range(),
                            aircraft_weapon_with_max_range.get_engagement_range(),
                        ),
                    )
                # 如果在探测范围且武器射程内，则发射武器
                elif (
                    distance_between_attacker_and_target_nm
                    <= attacker.get_detection_range() * 1.1
                    and distance_between_attacker_and_target_nm
                    <= aircraft_weapon_with_max_range.get_engagement_range() * 1.1
                ):
                    # 发射武器，默认发射一枚，可以根据需要调整发射数量
                    launched_weapon = (
                        attacker.get_weapon_with_highest_engagement_range()
                    )
                    if launched_weapon is None:
                        continue
                    launch_weapon(
                        self.current_scenario, attacker, target, launched_weapon, 1
                    )
                    attacker.target_id = target.id

    # --------------------- 位置更新 ---------------------

    # 更新所有飞机的位置：沿航线移动，消耗燃料，检查返航条件。
    def update_all_aircraft_position(self) -> None:
        for aircraft in self.current_scenario.aircraft:
            # 如果飞机在返航中且距离基地很近，执行降落
            if aircraft.rtb:
                aircraft_homebase = (
                    self.current_scenario.get_aircraft_homebase(aircraft.id)
                    if aircraft.home_base_id != ""
                    else self.current_scenario.get_closest_base_to_aircraft(aircraft.id)
                )
                if (
                    # 如果飞机已经到达基地，执行降落逻辑：将飞机从场景中移除，加入基地的飞机列表，并重置飞机的返航状态和航线。
                    aircraft_homebase is not None
                    and get_distance_between_two_points(
                        aircraft.latitude,
                        aircraft.longitude,
                        aircraft_homebase.latitude,
                        aircraft_homebase.longitude,
                    )
                    < 0.5
                ):
                    # 如果飞机已经到达基地，执行降落逻辑：将飞机从场景中移除，加入基地的飞机列表，并重置飞机的返航状态和航线。
                    self.land_aicraft(aircraft.id)
                    continue
            # 沿航线移动：如果有航线，朝航线上的下一个航点移动；如果到达航点则移除，继续朝下一个航点移动。            
            route = aircraft.route
            if len(route) > 0:
                next_waypoint = route[0]
                next_waypoint_latitude = next_waypoint[0]
                next_waypoint_longitude = next_waypoint[1]
                # 如果已经到达当前航点（距离 < 0.5 km），移除该航点
                if (
                    get_distance_between_two_points(
                        aircraft.latitude,
                        aircraft.longitude,
                        next_waypoint_latitude,
                        next_waypoint_longitude,
                    )
                    < 0.5
                ):
                    aircraft.latitude = next_waypoint_latitude
                    aircraft.longitude = next_waypoint_longitude
                    aircraft.route.pop(0)
                else:
                    # 否则朝航点方向移动一步
                    # 根据平台速度和当前位置与目标位置，计算下一步应到达的坐标。
                    next_aircraft_coordinates = get_next_coordinates(
                        aircraft.latitude,
                        aircraft.longitude,
                        next_waypoint_latitude,
                        next_waypoint_longitude,
                        aircraft.speed,
                    )
                    next_aircraft_latitude = next_aircraft_coordinates[0]
                    next_aircraft_longitude = next_aircraft_coordinates[1]
                    aircraft.latitude = next_aircraft_latitude
                    aircraft.longitude = next_aircraft_longitude
                    # 计算两点之间的方位角，更新飞机朝向
                    aircraft.heading = get_bearing_between_two_points(
                        aircraft.latitude,
                        aircraft.longitude,
                        next_waypoint_latitude,
                        next_waypoint_longitude,
                    )
            # 每秒消耗燃料
            aircraft.current_fuel -= aircraft.fuel_rate / 3600
            fuel_needed_to_return_to_base = self.get_fuel_needed_to_return_to_base(
                aircraft
            )
            # 燃料耗尽 → 坠毁
            if aircraft.current_fuel <= 0:
                self.remove_aircraft(aircraft.id)
            # 如果燃料不足返航且启用了"超出范围返航"条令，触发返航
            elif (
                self.current_scenario.check_side_doctrine(
                    aircraft.side_id, DoctrineType.AIRCRAFT_RTB_WHEN_OUT_OF_RANGE
                ) and
                aircraft.current_fuel < fuel_needed_to_return_to_base * 1.1
                and not aircraft.rtb
            ):
                self.aircraft_return_to_base(aircraft.id)

    # 更新所有舰船的位置：沿航线移动，消耗燃料。
    def update_all_ship_position(self) -> None:
        for ship in self.current_scenario.ships:
            route = ship.route
            if len(route) < 1:
                continue
            next_waypoint = route[0]
            next_waypoint_latitude = next_waypoint[0]
            next_waypoint_longitude = next_waypoint[1]
            # 到达航点 → 移除
            if (
                get_distance_between_two_points(
                    ship.latitude,
                    ship.longitude,
                    next_waypoint_latitude,
                    next_waypoint_longitude,
                )
                < 0.5
            ):
                ship.latitude = next_waypoint_latitude
                ship.longitude = next_waypoint_longitude
                ship.route.pop(0)
            else:
                # 朝航点移动一步
                next_ship_coordinates = get_next_coordinates(
                    ship.latitude,
                    ship.longitude,
                    next_waypoint_latitude,
                    next_waypoint_longitude,
                    ship.speed,
                )
                next_ship_latitude = next_ship_coordinates[0]
                next_ship_longitude = next_ship_coordinates[1]
                ship.latitude = next_ship_latitude
                ship.longitude = next_ship_longitude
                ship.heading = get_bearing_between_two_points(
                    ship.latitude,
                    ship.longitude,
                    next_waypoint_latitude,
                    next_waypoint_longitude,
                )
            # 每秒消耗燃料，耗尽则移除
            ship.current_fuel -= ship.fuel_rate / 3600
            if ship.current_fuel <= 0:
                self.current_scenario.ships.remove(ship)

    # 同步载机/载舰/设施上的武器坐标（未发射的库存武器位置跟随搭载平台）。
    def update_onboard_weapon_positions(self) -> None:
        for aircraft in self.current_scenario.aircraft:
            for weapon in aircraft.weapons:
                weapon.latitude = aircraft.latitude
                weapon.longitude = aircraft.longitude
        for facility in self.current_scenario.facilities:
            for weapon in facility.weapons:
                weapon.latitude = facility.latitude
                weapon.longitude = facility.longitude
        for ship in self.current_scenario.ships:
            for weapon in ship.weapons:
                weapon.latitude = ship.latitude
                weapon.longitude = ship.longitude

    # --------------------- 主仿真循环 ---------------------

    # 每仿真步更新一次游戏状态：时间 +1，依次执行防御、交战、任务、位置更新。
    def update_game_state(self) -> None:
        # 场景时间步进 1 秒
        self.current_scenario.current_time += 1

        # 自动防御（设施/舰船的反导和防空）
        self.facility_auto_defense()
        self.ship_auto_defense()
        # 空对空自动交战
        self.aircraft_air_to_air_engagement()

        # 更新巡逻任务中的单位航线
        self.update_units_on_patrol_mission()
        # 清理已完成的打击任务
        self.clear_completed_strike_missions()
        # 更新打击任务中的单位行为
        self.update_units_on_strike_mission()

        # 更新所有已发射武器的飞行状态
        for weapon in self.current_scenario.weapons:
            weapon_engagement(self.current_scenario, weapon)

        # 更新所有飞机和舰船的位置
        self.update_all_aircraft_position()
        self.update_all_ship_position()
        # 同步库存武器坐标
        self.update_onboard_weapon_positions()

    # --------------------- 动作处理 ---------------------

    # 处理外部传入的动作（字符串或字符串列表），通过 exec 执行 Python 代码。
    def handle_action(self, action: list | str) -> None:
        if not action or action == "" or len(action) == 0:
            return
        try:
            if isinstance(action, str):
                exec(f"{"self." if "self." not in action else ""}{action}")
            elif isinstance(action, list):
                for sub_action in action:
                    exec(f"{"self." if "self." not in sub_action else ""}{sub_action}")
        except Exception as e:
            print(e)

    # 获取当前场景作为观察（RL 环境的 observation）。
    def _get_observation(self) -> Scenario:
        return self.current_scenario

    # 获取附加信息（当前为空）。
    def _get_info(self) -> dict:
        return {}

    # RL 环境的标准 step 方法：处理动作 → 更新状态 → 返回 (obs, reward, terminated, truncated, info)。
    def step(self, action) -> Tuple[Scenario, float, bool, bool, None]:
        self.handle_action(action)
        self.update_game_state()
        terminated = False
        truncated = self.check_game_ended()
        reward = 0
        observation = self._get_observation()
        info = self._get_info()
        return observation, reward, terminated, truncated, info

    # RL 环境的标准 reset 方法：深拷贝恢复初始场景。
    def reset(self):
        self.current_scenario = copy.deepcopy(self.initial_scenario)
        assert len(self.current_scenario.sides) > 0
        self.current_side_id = self.current_scenario.sides[0].id
        self.scenario_paused = True
        self.current_attacker_id = ""

    # 检查游戏是否结束（当前始终返回 False，由外部控制终止条件）。
    def check_game_ended(self) -> bool:
        return False

    # --------------------- 场景导入导出 ---------------------

    # 将当前场景导出为字典格式（驼峰命名的 JSON 兼容格式）。
    def export_scenario(self) -> dict:
        scenario_json_string = self.current_scenario.toJson()
        scenario_json_no_underscores = to_camelcase(scenario_json_string)

        export_object = {
            "currentScenario": json.loads(scenario_json_no_underscores),
            "currentSideId": self.current_side_id,
            "selectedUnitId": "",
            "mapView": self.map_view,
        }

        return export_object

    # 从 JSON 字符串加载场景：解析并重建所有单位、任务、关系等对象。
    def load_scenario(self, scenario_string: str) -> None:
        import_object = json.loads(scenario_string)
        self.current_side_id = import_object["currentSideId"]
        self.map_view = import_object["mapView"]

        saved_scenario = import_object["currentScenario"]
        # 重建阵营
        saved_sides = []
        for side in saved_scenario["sides"]:
            saved_sides.append(
                Side(
                    id=side["id"],
                    name=side["name"],
                    total_score=side["totalScore"],
                    color=side["color"],
                )
            )
        # 重建场景对象
        loaded_scenario = Scenario(
            id=saved_scenario["id"],
            name=saved_scenario["name"],
            start_time=saved_scenario["startTime"],
            current_time=saved_scenario["currentTime"],
            duration=saved_scenario["duration"],
            sides=saved_sides,
            time_compression=saved_scenario["timeCompression"],
            relationships=Relationships(
                hostiles=(
                    saved_scenario["relationships"]["hostiles"]
                    if "relationships" in saved_scenario.keys()
                    and saved_scenario["relationships"]["hostiles"]
                    else {}
                ),
                allies=(
                    saved_scenario["relationships"]["allies"]
                    if "relationships" in saved_scenario.keys()
                    and saved_scenario["relationships"]["allies"]
                    else {}
                ),
            ),
            doctrine=saved_scenario["doctrine"]
        )
        # 重建飞机（含武器）
        for aircraft in saved_scenario["aircraft"]:
            aircraft_weapons = []
            if aircraft["weapons"]:
                for weapon in aircraft["weapons"]:
                    aircraft_weapons.append(
                        Weapon(
                            id=weapon["id"],
                            name=weapon["name"],
                            side_id=weapon["sideId"],
                            class_name=weapon["className"],
                            latitude=weapon["latitude"],
                            longitude=weapon["longitude"],
                            altitude=weapon["altitude"],
                            heading=weapon["heading"],
                            speed=weapon["speed"],
                            current_fuel=weapon["currentFuel"],
                            max_fuel=weapon["maxFuel"],
                            fuel_rate=weapon["fuelRate"],
                            range=weapon["range"],
                            route=weapon["route"],
                            side_color=weapon["sideColor"],
                            target_id=weapon["targetId"],
                            lethality=weapon["lethality"],
                            max_quantity=weapon["maxQuantity"],
                            current_quantity=weapon["currentQuantity"],
                        )
                    )
            loaded_scenario.aircraft.append(
                Aircraft(
                    id=aircraft["id"],
                    name=aircraft["name"],
                    side_id=aircraft["sideId"],
                    class_name=aircraft["className"],
                    latitude=aircraft["latitude"],
                    longitude=aircraft["longitude"],
                    altitude=aircraft["altitude"],
                    heading=aircraft["heading"],
                    speed=aircraft["speed"],
                    current_fuel=aircraft["currentFuel"],
                    max_fuel=aircraft["maxFuel"],
                    fuel_rate=aircraft["fuelRate"],
                    range=aircraft["range"],
                    route=aircraft["route"],
                    selected=aircraft["selected"],
                    side_color=aircraft["sideColor"],
                    weapons=aircraft_weapons,
                    home_base_id=aircraft["homeBaseId"],
                    rtb=aircraft["rtb"],
                    target_id=(
                        aircraft["targetId"] if "targetId" in aircraft.keys() else ""
                    ),
                )
            )
        # 重建空军基地（含驻扎飞机和飞机上的武器）
        for airbase in saved_scenario["airbases"]:
            airbase_aircraft = []
            for aircraft in airbase["aircraft"]:
                aircraft_weapons = []
                if aircraft["weapons"]:
                    for weapon in aircraft["weapons"]:
                        aircraft_weapons.append(
                            Weapon(
                                id=weapon["id"],
                                name=weapon["name"],
                                side_id=weapon["sideId"],
                                class_name=weapon["className"],
                                latitude=weapon["latitude"],
                                longitude=weapon["longitude"],
                                altitude=weapon["altitude"],
                                heading=weapon["heading"],
                                speed=weapon["speed"],
                                current_fuel=weapon["currentFuel"],
                                max_fuel=weapon["maxFuel"],
                                fuel_rate=weapon["fuelRate"],
                                range=weapon["range"],
                                route=weapon["route"],
                                side_color=weapon["sideColor"],
                                target_id=weapon["targetId"],
                                lethality=weapon["lethality"],
                                max_quantity=weapon["maxQuantity"],
                                current_quantity=weapon["currentQuantity"],
                            )
                        )
                new_aircraft = Aircraft(
                    id=aircraft["id"],
                    name=aircraft["name"],
                    side_id=aircraft["sideId"],
                    class_name=aircraft["className"],
                    latitude=aircraft["latitude"],
                    longitude=aircraft["longitude"],
                    altitude=aircraft["altitude"],
                    heading=aircraft["heading"],
                    speed=aircraft["speed"],
                    current_fuel=aircraft["currentFuel"],
                    max_fuel=aircraft["maxFuel"],
                    fuel_rate=aircraft["fuelRate"],
                    range=aircraft["range"],
                    route=aircraft["route"],
                    selected=aircraft["selected"],
                    side_color=aircraft["sideColor"],
                    weapons=aircraft_weapons,
                    home_base_id=aircraft["homeBaseId"],
                    rtb=aircraft["rtb"],
                    target_id=(
                        aircraft["targetId"] if "targetId" in aircraft.keys() else ""
                    ),
                )
                airbase_aircraft.append(new_aircraft)
            loaded_scenario.airbases.append(
                Airbase(
                    id=airbase["id"],
                    name=airbase["name"],
                    side_id=airbase["sideId"],
                    class_name=airbase["className"],
                    latitude=airbase["latitude"],
                    longitude=airbase["longitude"],
                    altitude=airbase["altitude"],
                    side_color=airbase["sideColor"],
                    aircraft=airbase_aircraft,
                )
            )
        # 重建设施（含武器）
        for facility in saved_scenario["facilities"]:
            facility_weapons = []
            if facility["weapons"]:
                for weapon in facility["weapons"]:
                    facility_weapons.append(
                        Weapon(
                            id=weapon["id"],
                            name=weapon["name"],
                            side_id=weapon["sideId"],
                            class_name=weapon["className"],
                            latitude=weapon["latitude"],
                            longitude=weapon["longitude"],
                            altitude=weapon["altitude"],
                            heading=weapon["heading"],
                            speed=weapon["speed"],
                            current_fuel=weapon["currentFuel"],
                            max_fuel=weapon["maxFuel"],
                            fuel_rate=weapon["fuelRate"],
                            range=weapon["range"],
                            route=weapon["route"],
                            side_color=weapon["sideColor"],
                            target_id=weapon["targetId"],
                            lethality=weapon["lethality"],
                            max_quantity=weapon["maxQuantity"],
                            current_quantity=weapon["currentQuantity"],
                        )
                    )
            loaded_scenario.facilities.append(
                Facility(
                    id=facility["id"],
                    name=facility["name"],
                    side_id=facility["sideId"],
                    class_name=facility["className"],
                    latitude=facility["latitude"],
                    longitude=facility["longitude"],
                    altitude=facility["altitude"],
                    range=facility["range"],
                    side_color=facility["sideColor"],
                    weapons=facility_weapons,
                )
            )
        # 重建已发射的武器
        for weapon in saved_scenario["weapons"]:
            loaded_scenario.weapons.append(
                Weapon(
                    id=weapon["id"],
                    name=weapon["name"],
                    side_id=weapon["sideId"],
                    class_name=weapon["className"],
                    latitude=weapon["latitude"],
                    longitude=weapon["longitude"],
                    altitude=weapon["altitude"],
                    heading=weapon["heading"],
                    speed=weapon["speed"],
                    current_fuel=weapon["currentFuel"],
                    max_fuel=weapon["maxFuel"],
                    fuel_rate=weapon["fuelRate"],
                    range=weapon["range"],
                    route=weapon["route"],
                    side_color=weapon["sideColor"],
                    target_id=weapon["targetId"],
                    lethality=weapon["lethality"],
                    max_quantity=weapon["maxQuantity"],
                    current_quantity=weapon["currentQuantity"],
                )
            )
        # 重建舰船（含舰载飞机和武器）
        for ship in saved_scenario["ships"]:
            ship_aircraft = []
            for aircraft in ship["aircraft"]:
                aircraft_weapons = []
                if aircraft["weapons"]:
                    for weapon in aircraft["weapons"]:
                        aircraft_weapons.append(
                            Weapon(
                                id=weapon["id"],
                                name=weapon["name"],
                                side_id=weapon["sideId"],
                                class_name=weapon["className"],
                                latitude=weapon["latitude"],
                                longitude=weapon["longitude"],
                                altitude=weapon["altitude"],
                                heading=weapon["heading"],
                                speed=weapon["speed"],
                                current_fuel=weapon["currentFuel"],
                                max_fuel=weapon["maxFuel"],
                                fuel_rate=weapon["fuelRate"],
                                range=weapon["range"],
                                route=weapon["route"],
                                side_color=weapon["sideColor"],
                                target_id=weapon["targetId"],
                                lethality=weapon["lethality"],
                                max_quantity=weapon["maxQuantity"],
                                current_quantity=weapon["currentQuantity"],
                            )
                        )
                new_aircraft = Aircraft(
                    id=aircraft["id"],
                    name=aircraft["name"],
                    side_id=aircraft["sideId"],
                    class_name=aircraft["className"],
                    latitude=aircraft["latitude"],
                    longitude=aircraft["longitude"],
                    altitude=aircraft["altitude"],
                    heading=aircraft["heading"],
                    speed=aircraft["speed"],
                    current_fuel=aircraft["currentFuel"],
                    max_fuel=aircraft["maxFuel"],
                    fuel_rate=aircraft["fuelRate"],
                    range=aircraft["range"],
                    route=aircraft["route"],
                    selected=aircraft["selected"],
                    side_color=aircraft["sideColor"],
                    weapons=aircraft_weapons,
                    home_base_id=aircraft["homeBaseId"],
                    rtb=aircraft["rtb"],
                    target_id=aircraft["targetId"] if aircraft["targetId"] else "",
                )
                ship_aircraft.append(new_aircraft)
            ship_weapons = []
            if ship["weapons"]:
                for weapon in ship["weapons"]:
                    ship_weapons.append(
                        Weapon(
                            id=weapon["id"],
                            name=weapon["name"],
                            side_id=weapon["sideId"],
                            class_name=weapon["className"],
                            latitude=weapon["latitude"],
                            longitude=weapon["longitude"],
                            altitude=weapon["altitude"],
                            heading=weapon["heading"],
                            speed=weapon["speed"],
                            current_fuel=weapon["currentFuel"],
                            max_fuel=weapon["maxFuel"],
                            fuel_rate=weapon["fuelRate"],
                            range=weapon["range"],
                            route=weapon["route"],
                            side_color=weapon["sideColor"],
                            target_id=weapon["targetId"],
                            lethality=weapon["lethality"],
                            max_quantity=weapon["maxQuantity"],
                            current_quantity=weapon["currentQuantity"],
                        )
                    )
            loaded_scenario.ships.append(
                Ship(
                    id=ship["id"],
                    name=ship["name"],
                    side_id=ship["sideId"],
                    class_name=ship["className"],
                    latitude=ship["latitude"],
                    longitude=ship["longitude"],
                    altitude=ship["altitude"],
                    heading=ship["heading"],
                    speed=ship["speed"],
                    current_fuel=ship["currentFuel"],
                    max_fuel=ship["maxFuel"],
                    fuel_rate=ship["fuelRate"],
                    range=ship["range"],
                    route=ship["route"],
                    side_color=ship["sideColor"],
                    weapons=ship_weapons,
                    aircraft=ship_aircraft,
                )
            )
        # 重建参考点
        if "referencePoints" in saved_scenario.keys():
            for reference_point in saved_scenario["referencePoints"]:
                loaded_scenario.reference_points.append(
                    ReferencePoint(
                        id=reference_point["id"],
                        name=reference_point["name"],
                        side_id=reference_point["sideId"],
                        latitude=reference_point["latitude"],
                        longitude=reference_point["longitude"],
                        altitude=reference_point["altitude"],
                        side_color=reference_point["sideColor"],
                    )
                )
        # 重建任务（根据是否有 assignedArea 区分巡逻任务和打击任务）
        if "missions" in saved_scenario.keys():
            for mission in saved_scenario["missions"]:
                if "assignedArea" in mission.keys():
                    assigned_area = []
                    for point in mission["assignedArea"]:
                        assigned_area.append(
                            ReferencePoint(
                                id=point["id"],
                                name=point["name"],
                                side_id=point["sideId"],
                                latitude=point["latitude"],
                                longitude=point["longitude"],
                                altitude=point["altitude"],
                                side_color=point["sideColor"],
                            )
                        )
                    loaded_scenario.missions.append(
                        PatrolMission(
                            id=mission["id"],
                            name=mission["name"],
                            side_id=mission["sideId"],
                            assigned_unit_ids=mission["assignedUnitIds"],
                            assigned_area=assigned_area,
                            active=mission["active"],
                        )
                    )
                else:
                    loaded_scenario.missions.append(
                        StrikeMission(
                            id=mission["id"],
                            name=mission["name"],
                            side_id=mission["sideId"],
                            assigned_unit_ids=mission["assignedUnitIds"],
                            assigned_target_ids=mission["assignedTargetIds"],
                            active=mission["active"],
                        )
                    )

        # 将加载的场景同时设为初始场景和当前场景
        self.initial_scenario = copy.deepcopy(loaded_scenario)
        self.current_scenario = loaded_scenario

    # --------------------- 录制 ---------------------

    # 开始录制当前场景。
    def start_recording(self):
        self.recorder.start_recording(self.current_scenario)

    # 录制一个步骤（如果达到录制间隔或强制录制）。
    def record_step(self, force: bool = False):
        if self.recorder.should_record(self.current_scenario.current_time) or force:
            self.recorder.record_step(
                json.dumps(self.export_scenario()), self.current_scenario.current_time
            )

    # 手动导出当前录制内容。
    def export_recording(self):
        self.recorder.export_recording(self.current_scenario.current_time)
