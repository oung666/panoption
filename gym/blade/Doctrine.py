from enum import Enum
from typing import TypedDict, Dict


# 作战条令类型枚举，定义游戏中可开关的战术行为规则。
class DoctrineType(str, Enum):
    # 飞机攻击敌方飞机
    AIRCRAFT_ATTACK_HOSTILE = "Aircraft attack hostile aircraft"
    # 飞机追击敌方飞机
    AIRCRAFT_CHASE_HOSTILE = "Aircraft chase hostile aircraft"
    # 飞机超出基地航程范围时自动返航
    AIRCRAFT_RTB_WHEN_OUT_OF_RANGE = "Aircraft RTB when out of range of homebase"
    # 飞机完成打击任务后自动返航
    AIRCRAFT_RTB_WHEN_STRIKE_MISSION_COMPLETE = "Aircraft RTB when strike mission complete"
    # 地对空导弹攻击敌方飞机
    SAM_ATTACK_HOSTILE = "SAMs attack hostile aircraft"
    # 舰船攻击敌方飞机
    SHIP_ATTACK_HOSTILE = "Ships attack hostile aircraft"


# 单一阵营的作战条令字典类型，键为条令名称，值为布尔值（是否启用）。
class SideDoctrine(TypedDict):
    AIRCRAFT_ATTACK_HOSTILE: bool
    AIRCRAFT_CHASE_HOSTILE: bool
    AIRCRAFT_RTB_WHEN_OUT_OF_RANGE: bool
    AIRCRAFT_RTB_WHEN_STRIKE_MISSION_COMPLETE: bool
    SAM_ATTACK_HOSTILE: bool
    SHIP_ATTACK_HOSTILE: bool


# 全局条令字典，键为阵营 ID（字符串），值为该阵营的条令配置。
Doctrine = Dict[str, SideDoctrine]
