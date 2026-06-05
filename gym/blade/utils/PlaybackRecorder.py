from typing import Optional
from blade.Scenario import Scenario
from blade.utils.utils import unix_to_local_time

# 单个录制文件的大小上限（MB），用于分片导出。
FILE_SIZE_LIMIT_MB = 10
# 对应字符数上限，超出时自动分片。
CHARACTER_LIMIT = FILE_SIZE_LIMIT_MB * 1024 * 1024
# 默认录制间隔（秒）
RECORDING_INTERVAL_SECONDS = 10


# 回放录制器，按固定间隔录制仿真步骤，支持自动分片导出。
class PlaybackRecorder:

    def __init__(
        self,
        record_every_seconds: Optional[int] = None,    # 录制间隔，默认 10 秒
        recording_export_path: Optional[str] = ".",      # 导出文件路径
    ) -> None:
        # 当前场景名称
        self.scenario_name: str = "New Scenario"
        # 上次录制时的场景时间
        self.current_scenario_time: int = 0
        # 当前录制的文本内容
        self.recording: str = ""
        # 当前录制片段的起始时间
        self.recording_start_time: int = 0
        # 录制间隔，未指定则使用默认值
        self.record_every_seconds: int = (
            record_every_seconds if record_every_seconds else RECORDING_INTERVAL_SECONDS
        )
        # 导出文件的目录路径
        self.recording_export_path: str = recording_export_path

    # 判断当前是否应该录制（距上次录制是否已超过间隔时间）。
    def should_record(self, current_scenario_time: int) -> bool:
        if (
            current_scenario_time - self.current_scenario_time
            >= self.record_every_seconds
        ):
            self.current_scenario_time = current_scenario_time
            return True
        return False

    # 重置录制状态。
    def reset(self):
        self.scenario_name = "New Scenario"
        self.recording = ""
        self.current_scenario_time = 0
        self.recording_start_time = 0

    # 开始录制，绑定到指定场景。
    def start_recording(self, scenario: Scenario):
        self.reset()
        self.scenario_name = scenario.name
        self.current_scenario_time = scenario.current_time
        self.recording_start_time = scenario.current_time

    # 记录一个仿真步骤的文本。
    # 当录制内容超出字符限制时，自动分片导出。
    def record_step(self, current_step: str, current_scenario_time: int):
        self.recording += current_step + "\n"
        if len(self.recording) > CHARACTER_LIMIT:
            # 超出限制时导出当前片段，重置录制缓冲区
            self.export_recording(current_scenario_time, self.recording_start_time)
            self.recording_start_time = current_scenario_time
            self.recording = ""

    # 将当前录制内容导出为 .jsonl 文件。
    def export_recording(
        self,
        recording_end_time_unix: int,
        recording_start_time_unix: Optional[int] = None,
    ):
        # 如果录制内容为空，则不导出
        if not self.recording:
            return

        if recording_start_time_unix is None:
            recording_start_time_unix = self.recording_start_time

        # 用起始和结束时间格式化文件名后缀
        formatted_recording_start_time = unix_to_local_time(
            recording_start_time_unix, separator=""
        )
        formatted_recording_end_time = unix_to_local_time(
            recording_end_time_unix, separator=""
        )
        suffix = f"{formatted_recording_start_time} - {formatted_recording_end_time}"

        # 生成文件名：路径/场景名 Recording 起始时间 - 结束时间.jsonl
        filename = f"{self.recording_export_path}/{self.scenario_name} Recording {suffix}.jsonl"

        with open(filename, "w", encoding="utf-8") as file:
            file.write(self.recording.rstrip("\n"))

        print(f"Recording exported to '{filename}'")

    # 以下为旧版压缩导出的注释代码，保留以供参考。
    """
    import gzip
    import json

    def export_recording(self) -> None:
        ...
    """
