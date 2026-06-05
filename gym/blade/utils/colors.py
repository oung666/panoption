from enum import Enum


# 阵营颜色枚举，提供地图上显示单位时可用的颜色列表。
class SIDE_COLOR(Enum):
    BLACK = "black"
    WHITE = "white"
    GRAY = "gray"
    SILVER = "silver"
    BEIGE = "beige"
    BROWN = "brown"
    MAROON = "maroon"
    RED = "red"
    DARKRED = "darkred"
    CORAL = "coral"
    SALMON = "salmon"
    ORANGE = "orange"
    GOLD = "gold"
    YELLOW = "yellow"
    OLIVE = "olive"
    LIME = "lime"
    LIGHTGREEN = "lightgreen"
    GREEN = "green"
    DARKGREEN = "darkgreen"
    AQUAMARINE = "aquamarine"
    TEAL = "teal"
    TURQUOISE = "turquoise"
    CYAN = "cyan"
    SKYBLUE = "skyblue"
    BLUE = "blue"
    DARKBLUE = "darkblue"
    NAVY = "navy"
    INDIGO = "indigo"
    PURPLE = "purple"
    PLUM = "plum"
    MAGENTA = "magenta"
    PINK = "pink"

    # 返回颜色名称的大写形式。
    def upper(self):
        return self.name.upper()


# 将颜色字符串或 None 转换为 SIDE_COLOR 枚举值。
# 如果传入 None 或空字符串，或颜色名不存在，则返回默认颜色（BLACK）。
def convert_color_name_to_side_color(
    color: str | None, return_if_error: SIDE_COLOR = SIDE_COLOR.BLACK
) -> SIDE_COLOR:
    if not color:
        return return_if_error

    # 将颜色名转为大写，匹配枚举键
    color_key = color.upper()
    try:
        return SIDE_COLOR[color_key]
    except KeyError:
        # 颜色名不存在时返回默认颜色
        return return_if_error
