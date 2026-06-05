import os
import gymnasium
import blade
from blade.Game import Game
from blade.Scenario import Scenario

# demo_folder 用来定位输入场景文件、录制文件以及最终导出的场景文件。
# 如果从仓库根目录运行脚本，可以改回 "./gym/scripts/simple_demo"。
# demo_folder = "./gym/scripts/simple_demo"
demo_folder = "."

# 创建 BLADE 游戏对象，并指定录制频率和录制文件导出目录。
game = Game(
    current_scenario=Scenario(),
    record_every_seconds=30,
    recording_export_path=demo_folder,
)

# 读取 simple_demo.json 场景配置，并加载到游戏对象中。
with open(f"{demo_folder}/simple_demo.json", "r") as scenario_file:
    game.load_scenario(scenario_file.read())

# 使用 gymnasium 创建 BLADE 环境，并把已经加载场景的 game 传进去。
env = gymnasium.make("blade/BLADE-v0", game=game, disable_env_checker=True)

# 重置环境，获得初始观测 observation 和附加信息 info。
observation, info = env.reset()

# 打印初始观测，便于人工检查场景中的单位状态。
env.unwrapped.pretty_print(observation)


def simple_scripted_agent(observation):
    """根据当前观测返回一个脚本化动作字符串。"""

    # 从蓝方机场起飞一架飞机，参数是机场 ID。
    sample_launch_aircraft_action = (
        "launch_aircraft_from_airbase('05dbcb4c-dcf8-4125-ba2e-3a6fce8b33a3')"
    )

    # 下面这些 ID 来自场景文件：飞机 ID、武器 ID、红方目标 ID。
    launched_aircraft_id = "fbcaa81c-bb50-470b-9e6d-81cd825b1fd0"
    launched_aircraft_weapon_id = "1767322b-106b-418f-bd17-381590d5f916"

    # 第一段航路点：让飞机先飞到红方目标附近。
    first_target_position = [10.9, -22.7]
    first_move_aircraft_action = f"move_aircraft('{launched_aircraft_id}', [[{first_target_position[0]}, {first_target_position[1]}]])"

    # 第二段航路点：攻击后继续向敌方机场方向渗透。
    second_target_position = [15.75, -8.97]
    second_move_aircraft_action = f"move_aircraft('{launched_aircraft_id}', [[{second_target_position[0]}, {second_target_position[1]}]])"
    red_target_id = "e0d4547d-9921-4580-bef9-5026f371cb9e"

    # 构造攻击动作：飞机使用指定武器攻击红方目标，最后的 5 是攻击参数。
    attack_target_action = f"handle_aircraft_attack('{launched_aircraft_id}', '{red_target_id}', '{launched_aircraft_weapon_id}', 5)"

    # 构造返航动作：让飞机返回基地。
    return_to_base_action = f"aircraft_return_to_base('{launched_aircraft_id}')"

    # 计算当前仿真已经推进了多少个时间步。
    start_time = observation.start_time
    current_time_step = observation.current_time - start_time

    # 在当前观测中的飞机列表里，查找刚才计划起飞的那架飞机。
    launched_aircraft = None
    aircraft = [ac for ac in observation.aircraft if ac.id == launched_aircraft_id]
    if len(aircraft) > 0:
        launched_aircraft = aircraft[0]

    # 第 0 个时间步：从蓝方机场起飞。
    if current_time_step == 0:
        return sample_launch_aircraft_action

    # 第 1 个时间步：把已经起飞的飞机派往第一个航路点。
    elif current_time_step == 1:
        return first_move_aircraft_action

    # 飞机已经深入到敌方机场附近，并且还没有返航时，命令其返航。
    elif (
        launched_aircraft != None
        and launched_aircraft.latitude > 15
        and launched_aircraft.longitude > -11
        and launched_aircraft.rtb == False
    ):
        return return_to_base_action

    # 飞机接近第一个航路点且未返航时，继续移动到第二个航路点。
    elif (
        launched_aircraft != None
        and launched_aircraft.latitude > 10
        and launched_aircraft.longitude > -23
        and launched_aircraft.rtb == False
    ):
        return second_move_aircraft_action

    # 飞机进入攻击范围且未返航时，对红方目标发起攻击。
    elif (
        launched_aircraft != None
        and launched_aircraft.latitude > 0
        and launched_aircraft.longitude > -33
        and launched_aircraft.rtb == False
    ):
        return attack_target_action
    else:
        # 没有满足任何触发条件时，返回空字符串表示本时间步不执行动作。
        return ""


# 清理上一次运行产生的 simple_demo_t*.json 和 jsonl 录制文件。
for filename in os.listdir(demo_folder):
    if (
        filename.endswith(".json") and "simple_demo_t" in filename
    ) or filename.endswith(".jsonl"):
        os.remove(f"{demo_folder}/{filename}")

# 开始录制仿真过程，并记录初始状态。
game.start_recording()
game.record_step()

# 运行固定数量的仿真步。
steps = 35000
for step in range(steps):
    # 根据当前观测生成动作，并将动作提交给环境推进一步。
    action = simple_scripted_agent(observation)
    observation, reward, terminated, truncated, info = env.step(action=action)

    # 如需观察每一步的状态，可以取消下一行注释。
    # env.unwrapped.pretty_print(observation)

    # 记录当前仿真状态，用于后续回放或分析。
    game.record_step()

# 导出最终场景；此时蓝方飞机预期应处于返航状态。
env.unwrapped.export_scenario(
    f"{demo_folder}/simple_demo_t{steps}.json"
)

# 导出完整录制结果。
game.export_recording()
