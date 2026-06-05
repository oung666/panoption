import argparse
import gymnasium
import numpy as np
from blade.Game import Game
from blade.Scenario import Scenario
from stable_baselines3 import PPO
from gymnasium.spaces import Box
from blade.utils.utils import get_bearing_between_two_points

# 调试开关：为 True 时打印详细 reward 分解和 black_box 日志
DEBUG = False
# 输出目录
demo_folder = "./gym/scripts/stable_baselines"

parser = argparse.ArgumentParser(description="Train or evaluate a BLADE PPO aircraft agent.")
parser.add_argument("--scenario", default=f"{demo_folder}/scen.json")
parser.add_argument("--target-lat", type=float, default=4.5)
parser.add_argument("--target-lon", type=float, default=5.5)
parser.add_argument("--model-name", default="default_hyper_ppo_aircraft")
parser.add_argument("--train-steps", type=int, default=350_00)
parser.add_argument("--record-steps", type=int, default=35000)
parser.add_argument("--learn", action="store_true", dest="learn")
parser.add_argument("--no-learn", action="store_false", dest="learn")
parser.add_argument("--no-evaluate", action="store_false", dest="evaluate")
parser.set_defaults(learn=False, evaluate=True)
args = parser.parse_args()
goal_coordinates = np.array([args.target_lat, args.target_lon])

# 创建游戏实例，初始化为空场景，每 30 秒录制一步
game = Game(
    current_scenario=Scenario(),
    record_every_seconds=30,
    recording_export_path=demo_folder,
)
# 从 JSON 文件加载预设场景（包含飞机初始位置等）
with open(args.scenario, "r") as scenario_file:
    game.load_scenario(scenario_file.read())

# 观测空间：当前位置、目标相对向量、距离目标的欧氏距离。
observation_space = Box(
    low=np.array([-90.0, -180.0, -180.0, -360.0, 0.0]),
    high=np.array([90.0, 180.0, 180.0, 360.0, 500.0]),
    dtype=np.float64,
)
# 动作空间：下一段局部航路点偏移量，避免模型反复输出 [0, 0] 这种全局坐标。
action_space = Box(
    low=np.array([-2.0, -2.0]), high=np.array([2.0, 2.0]), dtype=np.float64
)

TRAINING_AIRCRAFT_NAME = "Blue Trainee"


def get_training_aircraft(observation: Scenario):
    aircraft = [
        ac for ac in observation.aircraft if ac.name == TRAINING_AIRCRAFT_NAME
    ]
    if len(aircraft) > 0:
        return aircraft[0]

    aircraft = [
        ac
        for ac in observation.aircraft
        if getattr(ac.side_color, "value", ac.side_color) == "blue"
    ]
    if len(aircraft) > 0:
        return aircraft[0]

    return observation.aircraft[0] if len(observation.aircraft) > 0 else None


def action_transform_fnc(observation: Scenario, action: np.ndarray):
    """将 RL 模型输出的坐标 [lat, lon] 转换为游戏指令字符串。
    同时将当前状态记录到飞机的 black_box 中，供 reward 计算使用。
    """
    aircraft = get_training_aircraft(observation)
    if aircraft is None:
        return ""
    start_latitude = aircraft.latitude
    start_longitude = aircraft.longitude

    bounded_action = np.clip(action, action_space.low, action_space.high)
    destination_latitude = float(
        np.clip(start_latitude + bounded_action[0], -90.0, 90.0)
    )
    destination_longitude = float(
        np.clip(start_longitude + bounded_action[1], -180.0, 180.0)
    )

    # 记录本次动作前的飞机状态（位置、航向、速度、燃油）
    aircraft.black_box.log(
        timestamp=0,
        latitude=start_latitude,
        longitude=start_longitude,
        heading=get_bearing_between_two_points(
            start_latitude=start_latitude,
            start_longitude=start_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
        ),
        speed=aircraft.speed,
        fuel=aircraft.current_fuel,
    )
    if DEBUG:
        print(f"log: {aircraft.black_box.get_last_log_pp()}")

    # 构造 move_aircraft 指令字符串，发给游戏引擎执行
    action = f"move_aircraft('{aircraft.id}', [[{destination_latitude}, {destination_longitude}]])"
    return action


def observation_filter_fnc(observation: Scenario):
    """从完整场景中提取 RL 模型所需的观测向量：[飞机纬度, 飞机经度]。"""
    aircraft = get_training_aircraft(observation)
    if aircraft == None:
        return np.zeros(5, dtype=np.float64)
    delta = goal_coordinates - np.array([aircraft.latitude, aircraft.longitude])
    distance = euclidean_distance(
        [aircraft.latitude, aircraft.longitude], goal_coordinates
    )
    return np.array(
        [
            aircraft.latitude,
            aircraft.longitude,
            delta[0],
            delta[1],
            distance,
        ],
        dtype=np.float64,
    )


def euclidean_distance(start_coord, end_coord):
    """计算两点之间的欧几里得距离（简化版，适用于小范围经纬度）。"""
    return np.sqrt(
        (end_coord[0] - start_coord[0]) ** 2 + (end_coord[1] - start_coord[1]) ** 2
    )


def reward_filter_fnc(observation: Scenario):
    """计算当前步的奖励值。
    奖励由三部分组成：
    1. 距离进步奖励：飞机向目标靠近了多少
    2. 航向对齐奖励：飞机是否朝向目标飞行
    3. 航向平滑惩罚：惩罚频繁大幅转向
    """
    # 计算一组数值的均方变化量（角度差需处理 360° 环绕）
    def mean_squared_change(values):
        differences = np.abs(np.diff(values))
        differences = np.where(differences > 180, 360 - differences, differences)
        return np.mean(differences**2) if len(differences) > 0 else 0

    # 另一种衡量航向变化的方法：总变化量 / 标准差（备用）
    def smoothness_index(values):
        differences = np.diff(values)
        differences = np.where(differences > 180, 360 - differences, differences)
        total_variation = np.sum(differences)
        std_dev = np.std(differences)
        return total_variation / (std_dev + 1e-8) if len(differences) > 0 else 0

    aircraft = get_training_aircraft(observation)

    if aircraft is None:
        return -1000  # 飞机不存在时给一个有限的大惩罚，避免训练数值发散

    # 获取上一步记录的位置和航向
    previous_log = aircraft.black_box.get_last_log()
    previous_latitude = previous_log.get("latitude")
    previous_longitude = previous_log.get("longitude")
    previous_heading = previous_log.get("heading")

    # 上一步到目标的距离 vs 当前到目标的距离
    previous_distance = euclidean_distance(
        [previous_latitude, previous_longitude], goal_coordinates
    )
    current_distance = euclidean_distance(
        [aircraft.latitude, aircraft.longitude], goal_coordinates
    )

    # 各项 reward 的缩放因子
    scaling_factors = {
        "distance": 50,
        "exp_progress": 100,
        "heading_align": 5,
        "distance_to_goal": 0.2,
        "goal_bonus": 5000,
        "step": 1,
        "heading_smoothness": 0.001,
    }

    # 距离进步奖励：距离缩短越多，奖励越大
    distance_progress_reward = scaling_factors.get("distance") * (
        previous_distance - current_distance
    )
    distance_to_goal_penalty = -scaling_factors.get("distance_to_goal") * current_distance
    goal_bonus = scaling_factors.get("goal_bonus") if current_distance < 0.1 else 0
    step_penalty = -scaling_factors.get("step")
    # 指数距离奖励（被注释掉）：目标越近奖励越大
    exponential_reward = np.exp(-current_distance) * scaling_factors.get("exp_progress")

    # 航向对齐奖励：机头朝向与目标方向的偏差越小，奖励越大
    target_heading = get_bearing_between_two_points(
        aircraft.latitude, aircraft.longitude, goal_coordinates[0], goal_coordinates[1]
    )
    heading_difference = abs((previous_heading - target_heading + 180) % 360 - 180)
    heading_alignment_reward = (1 - heading_difference / 180.0) * scaling_factors.get(
        "heading_align"
    )

    # 航向平滑惩罚：航向变化越剧烈，惩罚越大（鼓励平稳飞行）
    headings = [
        log_entry["heading"]
        for log_entry in aircraft.black_box._logs
        if "heading" in log_entry
    ]
    heading_smoothness_penalty = -mean_squared_change(headings) * scaling_factors.get(
        "heading_smoothness"
    )

    # 总奖励 = 距离进步 + 航向对齐 - 航向变化惩罚
    total_reward = (
        distance_progress_reward
        + distance_to_goal_penalty
        + goal_bonus
        + step_penalty
        # + exponential_reward
        + heading_alignment_reward
        + heading_smoothness_penalty
    )

    if DEBUG:
        print(f"Reward Breakdown |-------------------------------------------")
        print(f"  Distance Progress Reward: {distance_progress_reward}")
        # print(f"  Exponential Reward: {exponential_reward}")
        print(f"  Heading Alignment Reward: {heading_alignment_reward}")
        print(f"  Heading Smoothness Penalty: {heading_smoothness_penalty}")
        print(f"  Total Reward: {total_reward}")
        print(f"------------------------------------------------------------")

    return total_reward


def termination_filter_fnc(observation: Scenario):
    """终止条件：当飞机距离目标点小于 0.1 度时，episode 结束。"""
    aircraft = get_training_aircraft(observation)

    if aircraft == None:
        return True
    else:
        distance = euclidean_distance(
            [aircraft.latitude, aircraft.longitude], goal_coordinates
        )

    terminated = distance < 0.1
    return terminated


def evaluate_agent(model, env, num_episodes=1):
    """评估训练好的智能体：运行 num_episodes 个 episode，返回平均 reward 和标准差。"""
    total_rewards = []
    for _ in range(num_episodes):
        obs, _ = env.reset()
        episode_reward = 0
        done = False
        while not done:
            action, _ = model.predict(obs)
            obs, reward, terminated, truncated, _ = env.step(action)
            episode_reward += reward
            done = terminated or truncated

        # 导出评估结果场景
        env.unwrapped.export_scenario(f"{demo_folder}/scen_x.json")

        total_rewards.append(episode_reward)
    return np.mean(total_rewards), np.std(total_rewards)


# 注册并创建 BLADE 强化学习环境
env = gymnasium.make(
    "blade/BLADE-v0",
    game=game,
    observation_space=observation_space,
    action_space=action_space,
    action_transform_fnc=action_transform_fnc,          # 动作转换函数
    observation_filter_fnc=observation_filter_fnc,       # 观测过滤函数
    reward_filter_fnc=reward_filter_fnc,                 # 奖励计算函数
    termination_filter_fnc=termination_filter_fnc,       # 终止判断函数
)

# 创建 PPO 模型（多层感知机策略）
model = PPO(
    "MlpPolicy",
    env,
    verbose=1,              # 训练时打印进度条
    device="cpu",           # 使用 CPU 训练
    learning_rate=3e-4,     # 学习率
    # clip_range=0.2,       # PPO 裁剪范围（默认 0.2）
    n_steps=512,            # 每次策略更新前收集的步数
    batch_size=32,          # 小批量大小
    # gamma=0.95,           # 折扣因子（默认 0.99）
    # gae_lambda=0.9,       # GAE λ 参数（默认 0.95）
    # ent_coef=0.01,        # 熵系数（默认 0.0）
    # vf_coef=0.5,          # 价值函数损失系数（默认 0.5）
    # max_grad_norm=0.5,    # 梯度裁剪阈值（默认 0.5）
)

learn = args.learn   # 是否执行训练
evaluate = args.evaluate  # 是否执行评估
default_hyper_params_filename = args.model_name

if learn:
    # 训练 350,000 步
    model.learn(total_timesteps=args.train_steps)
    # 保存训练好的模型
    model.save(f"{demo_folder}/{default_hyper_params_filename}.zip")

if evaluate:
    import os

    # 加载之前训练好的模型（model0、model1 被注释掉，仅比较 model2）
    # model0 = PPO.load(f"{demo_folder}/muh_model.zip", device="cpu")
    # model1 = PPO.load(f"{demo_folder}/ppo_aircraft.zip", device="cpu")
    eval_model = PPO.load(
        f"{demo_folder}/{default_hyper_params_filename}", env=env, device="cpu"
    )

    # 分别评估三个模型（已注释的两个保留用于对比实验）
    # mean, std = evaluate_agent(model0, env)
    # print(f"mean: {mean} std: {std}")
    # mean, std = evaluate_agent(model1, env)
    # print(f"mean: {mean} std: {std}")

    mean, std = evaluate_agent(eval_model, env)
    print(f"mean: {mean} std: {std}")

    # 清理旧的评估场景文件
    for filename in os.listdir(demo_folder):
        if filename.endswith(".json") and (
            "scen_t" in filename or "scen_x" in filename
        ):
            os.remove(f"{demo_folder}/{filename}")

    # 生成回放：直接使用底层环境，避免 Gymnasium 的 2000 步 TimeLimit 自动 reset。
    obs, _ = env.unwrapped.reset()

    game.start_recording()
    game.record_step(force=True)
    steps = args.record_steps
    for step in range(steps):
        action, _states = eval_model.predict(obs, deterministic=True)  # deterministic=True 使用确定性策略（不采样）
        obs, reward, terminated, truncated, info = env.unwrapped.step(action)
        game.record_step()
        if terminated:
            break

    # 导出最终场景和录制文件
    env.unwrapped.export_scenario(
        f"{demo_folder}/scen_t{steps}.json"
    )
    game.export_recording()
