# ===================== 地球与单位换算常量 =====================

# 地球半径（公里）
EARTH_RADIUS_KM = 6371
# 地球半径（米）
EARTH_RADIUS_M = 6371008.8
# 1 海里 = 1852 米
NAUTICAL_MILES_TO_METERS = 1852
# 1 公里 ≈ 0.539957 海里
KILOMETERS_TO_NAUTICAL_MILES = 0.539957
# 默认地图投影编码（Web Mercator）
DEFAULT_OL_PROJECTION_CODE = "EPSG:3857"

# ===================== 游戏速度与延迟 =====================

# 时间压缩倍率对应的每步延迟（毫秒）
GAME_SPEED_DELAY_MS = {
    1: 1000,   # 1× 速度：每秒一步
    2: 500,    # 2× 速度：每 500ms 一步
    4: 250,    # 4× 速度：每 250ms 一步
    8: 125,    # 8× 速度：每 125ms 一步
    100: 0,    # 极速模式：无延迟
}

# ===================== 强化学习环境参数 =====================

# 观察空间的最大字符数
BLADE_ENV_OBSERVATION_SPACE_MAX_CHARACTERS = 100000
# 动作空间的最大字符数
BLADE_ENV_ACTION_SPACE_MAX_CHARACTERS = 100000
