import os
import re
import subprocess
import sys

from .BaseTool import Tool


class MTKClientTool(Tool):
    def __init__(self, path: str = None):
        super().__init__(path)
        self.last_error = None

    @property
    def common_paths(self) -> dict[str, list[str]]:
        return {}

    @property
    def name(self) -> str:
        return "MTKClient"

    @property
    def runnable_files(self) -> dict[str, list[str]]:
        return {}

    @property
    def mirrors(self) -> list[str]:
        return [
            "https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip",
            "https://ghproxy.com/https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip"
        ]

    def is_available(self, system: str = None, path: str = None) -> bool:
        return os.path.exists(self.get_main_program(path))


    def get_main_program(self, path: str = None) -> str:
        if path is None:
            path = self.get_path()
        return os.path.join(path, os.path.join("mtkclient-main", "mtk.py"))

    def detect_devices(self):
        try:
            # 使用更长的超时时间，因为检测可能需要一些时间
            result = subprocess.run([sys.executable, self.get_main_program(), "detect"],
                                    capture_output=True,
                                    text=True,
                                    timeout=30,  # 增加超时时间
                                    encoding='utf-8',
                                    errors='ignore')

            # 解析MTK设备 - 使用更健壮的正则表达式匹配
            devices = []

            # 匹配端口信息
            port_pattern = r"Found Port:\s*(\S+)\s"
            port_matches = re.findall(port_pattern, result.stdout)

            # 匹配设备信息
            device_pattern = r"Device detected:\s*(.+)"
            device_matches = re.findall(device_pattern, result.stdout)

            # 匹配芯片信息
            chip_pattern = r"HW Chip:\s*(.+)"
            chip_matches = re.findall(chip_pattern, result.stdout)

            # 组合设备信息
            if port_matches:
                port = port_matches[0]
                device_info = "MTK Device"

                if device_matches:
                    device_info = device_matches[0]
                    if chip_matches:
                        device_info += f" ({chip_matches[0]})"

                devices.append((port, device_info))

            return devices
        except Exception as e:
            self.last_error = str(e)
            return []

