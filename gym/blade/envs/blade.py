import json
import gymnasium as gym
from gymnasium.spaces import Text

from blade.Game import Game
from blade.Scenario import Scenario
from blade.utils.constants import (
    BLADE_ENV_OBSERVATION_SPACE_MAX_CHARACTERS,
    BLADE_ENV_ACTION_SPACE_MAX_CHARACTERS,
)


# BLADE 环境的 Gymnasium 封装类，将仿真游戏包装成标准强化学习环境。
class BLADE(gym.Env):

    def __init__(
        self,
        render_mode=None,
        game: Game = None,
        observation_space=None,
        action_space=None,
        action_transform_fnc=None,
        observation_filter_fnc=None,
        reward_filter_fnc=None,
        termination_filter_fnc=None,
    ):
        # 如果没有传入自定义观察空间，则使用默认的文本观察空间。
        if observation_space is None:
            self.observation_space = Text(
                max_length=BLADE_ENV_OBSERVATION_SPACE_MAX_CHARACTERS
            )
        else:
            self.observation_space = observation_space
        # 如果没有传入自定义动作空间，则使用默认的文本动作空间。
        if action_space is None:
            self.action_space = Text(max_length=BLADE_ENV_ACTION_SPACE_MAX_CHARACTERS)
        else:
            self.action_space = action_space
        # 可选的转换函数，用于预处理或结构化动作/观察/奖励/终止信号。
        self.action_transform_fnc = action_transform_fnc
        self.observation_filter_fnc = observation_filter_fnc
        self.reward_filter_fnc = reward_filter_fnc
        self.termination_filter_fnc = termination_filter_fnc
        self.render_mode = render_mode
        # 底层的仿真游戏实例，所有仿真逻辑由 Game 对象负责。
        self.game = game

    # 获取当前环境的观察值，可以选择性地经过过滤函数处理。
    def _get_obs(self):
        obs = self.game._get_observation()
        if self.observation_filter_fnc is not None:
            obs = self.observation_filter_fnc(obs)
        return obs

    # 获取当前环境的附加信息。
    def _get_info(self):
        return self.game._get_info()

    # 重置环境，将仿真恢复到初始状态。
    def reset(self, seed=None, options=None):
        self.game.reset()
        observation = self._get_obs()
        info = self._get_info()
        return observation, info

    # 执行一步环境交互，返回新的观察、奖励、终止标识和信息。
    def step(self, action):
        # 如果传入了动作转换函数，先将原始动作转换为游戏可识别的格式。
        if self.action_transform_fnc is not None:
            action = self.action_transform_fnc(self.game.current_scenario, action)
        # 调用底层游戏的步进逻辑，获得仿真执行结果。
        observation, reward, terminated, truncated, info = self.game.step(action=action)
        # 依次应用奖励、终止和观察的过滤函数。
        if self.reward_filter_fnc is not None:
            reward = self.reward_filter_fnc(observation)
        if self.termination_filter_fnc is not None:
            terminated = self.termination_filter_fnc(observation)
        if self.observation_filter_fnc is not None:
            observation = self.observation_filter_fnc(observation)
        return observation, reward, terminated, truncated, info

    # 将当前场景导出为 JSON 文件。
    def export_scenario(self, file_path: str = None):
        if file_path == None:
            file_path = f"{self.game.current_scenario.name}_end_state.json"
        with open(file_path, "w") as scenario_file:
            json.dump(self.game.export_scenario(), scenario_file)

    # 以可读格式打印当前场景的关键信息。
    def pretty_print(self, observation: Scenario = None):
        if observation == None:
            observation = self._get_obs()
        print("Current Time: " + str(observation.current_time))
