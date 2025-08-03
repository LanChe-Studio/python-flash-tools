import os
import platform
import subprocess
import time

from .BaseTool import Tool


class PlatformTools(Tool):
    def __init__(self, path: str = None):
        super().__init__(path)
        self.last_error = None

    @property
    def common_paths(self) -> dict[str, list[str]]:
        return {
            "darwin": [
                "/usr/local/bin",
                "/opt/homebrew/bin",  # Apple Silicon 常见路径
                "/usr/bin",
                os.path.expanduser("~/Library/Android/sdk/platform-tools"),
                os.path.expanduser("~/Android/Sdk/platform-tools")
            ],
            "linux": [
                "/usr/local/bin",
                "/usr/bin",
                os.path.expanduser("~/Android/Sdk/platform-tools"),
                os.path.expanduser("~/android-sdk/platform-tools")
            ],
            "windows": [
                r"C:\Android\platform-tools",
                r"C:\Program Files\Android\platform-tools",
                r"C:\Users\%USERNAME%\AppData\Local\Android\Sdk\platform-tools"
            ]
        }

    @property
    def runnable_files(self) -> dict[str, list[str]]:
        return {
            'darwin': [
                'platform-tools/adb',
                'platform-tools/fastboot'
            ],
            'linux': [
                'platform-tools/adb',
                'platform-tools/fastboot'
            ],
            'windows': [
                'platform-tools\\adb.exe',
                'platform-tools\\fastboot.exe'
            ]
        }

    @property
    def mirrors(self) -> list[str]:
        return [
            "https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            "https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            "https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]

    @property
    def name(self) -> str:
        return "PlatformTools"

    def is_available(self, system: str = None, path: str = None) -> bool:
        if system is None:
            system = platform.system().lower()
        if path is None:
            path = self.get_path()
        if not os.path.isdir(path):
            return False

        try:
            result = subprocess.run([self.get_adb_path(system, path), 'version'],
                                    capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore',
                                    timeout=2)
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError):
            return False

        try:
            result = subprocess.run([self.get_fastboot_path(system, path), '--version'],
                                    capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore',
                                    timeout=2)
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError, OSError):
            return False
        return False

    def get_adb_path(self, system: str = None, path: str = None) -> str:
        if system is None:
            system = platform.system().lower()
        if path is None:
            path = self.get_path()
        return os.path.join(path, self.get_runnable_files(system)[0])

    def get_fastboot_path(self, system: str = None, path: str = None) -> str:
        if system is None:
            system = platform.system().lower()
        if path is None:
            path = self.get_path()
        return os.path.join(path, self.get_runnable_files(system)[1])

    def get_adb_stat(self) -> bool:
        try:
            result = subprocess.run(
                [self.get_adb_path(), "start-server"],
                capture_output=True,
                text=True
            )
            print(result.stdout.strip())
            return result.returncode == 0
        except Exception as e:
            self.last_error = f"启动 ADB server 失败: {e}"
            return False

    def get_adb_devices(self):
        """获取设备列表"""
        if not self.get_adb_stat():
            return []

        try:
            result = subprocess.run([self.get_adb_path(), "devices"],
                                    capture_output=True,
                                    text=True,
                                    encoding='utf-8',
                                    errors='ignore',
                                    timeout=10)
            if result.returncode == 0:
                # 解析设备列表
                devices = []
                for line in result.stdout.splitlines():
                    if line and not line.startswith('List of') and '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            devices.append((parts[0], parts[1]))
                return devices
        except Exception as e:
            self.last_error = str(e)

        return []

    def get_fastboot_devices(self):
        """获取fastboot设备列表"""
        try:
            result = subprocess.run([self.get_fastboot_path(), "devices"],
                                    capture_output=True,
                                    text=True,
                                    encoding='utf-8',
                                    errors='ignore',
                                    timeout=10)
            if result.returncode == 0:
                # 解析设备列表
                devices = []
                for line in result.stdout.splitlines():
                    if line and '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            devices.append((parts[0], parts[1]))
                return devices
        except Exception as e:
            self.last_error = str(e)

        return []

    def execute_adb_command(self, command):
        """执行ADB命令"""

        try:
            result = subprocess.run([self.get_adb_path()] + command.split(),
                                    capture_output=True,
                                    text=True,
                                    timeout=60,
                                    encoding='utf-8',
                                    errors='ignore')

            # 检查授权问题
            output = result.stdout + result.stderr
            if "unauthorized" in output or "device unauthorized" in output:
                return {
                    'success': False,
                    'output': result.stdout,
                    'error': "设备未授权，请检查设备屏幕并确认授权"
                }

            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
        except Exception as e:
            self.last_error = str(e)
            return None

    def execute_fastboot_command(self, command):
        """执行Fastboot命令"""

        try:
            result = subprocess.run([self.get_fastboot_path()] + command.split(),
                                    capture_output=True,
                                    text=True,
                                    timeout=60,
                                    encoding='utf-8',
                                    errors='ignore')
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
        except Exception as e:
            self.last_error = str(e)
            return None

    def adb_reboot(self, mode=None):
        """重启设备"""

        cmd = [self.get_adb_path(), "reboot"]
        if mode is not None:
            cmd.append(mode)

        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=15, encoding='utf-8', errors='ignore')

            # 检查授权问题
            output = result.stdout + result.stderr
            if "unauthorized" in output or "device unauthorized" in output:
                self.last_error = "设备未授权，请检查设备屏幕并确认授权"
                return False, self.last_error

            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "未知错误"
                return False, self.last_error
            return True, ""
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def fastboot_reboot(self):
        """Fastboot模式重启"""

        try:
            result = subprocess.run([self.get_fastboot_path(), "reboot"],
                                    capture_output=True,
                                    text=True,
                                    encoding='utf-8',
                                    errors='ignore',
                                    timeout=15)

            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "未知错误"
                return False, self.last_error
            return True, ""
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def unlock_bootloader(self):
        """解锁Bootloader"""
        try:
            result = subprocess.run([self.get_fastboot_path(), "flashing", "unlock"],
                                    capture_output=True,
                                    text=True,
                                    timeout=60,
                                    encoding='utf-8',
                                    errors='ignore')
            if result.returncode != 0:
                result = subprocess.run([self.get_fastboot_path(), "oem", "unlock"],
                                        capture_output=True,
                                        text=True,
                                        timeout=60,
                                        encoding='utf-8',
                                        errors='ignore')

            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "解锁失败"
                return False, self.last_error
            return True, ""
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def lock_bootloader(self):
        """锁定Bootloader"""

        try:
            result = subprocess.run([self.get_fastboot_path(), "flashing", "lock"],
                                    capture_output=True,
                                    text=True,
                                    timeout=60,
                                    encoding='utf-8',
                                    errors='ignore')
            if result.returncode != 0:
                result = subprocess.run([self.get_fastboot_path(), "oem", "lock"],
                                        capture_output=True,
                                        text=True,
                                        timeout=60,
                                        encoding='utf-8',
                                        errors='ignore')

            if result.returncode != 0:
                self.last_error = result.stderr.strip() or result.stdout.strip() or "锁定失败"
                return False, self.last_error
            return True, ""
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)

    def flash_partition(self, partition, image_path):
        """刷入分区"""

        try:
            # 增加重试机制
            max_retries = 5
            retry_count = 0
            success = False
            error_log = []

            while not success and retry_count < max_retries:
                try:
                    # 检查设备连接
                    devices = self.get_fastboot_devices()
                    if not devices:
                        error_log.append(f"第{retry_count + 1}次重试: 未检测到Fastboot设备")
                        time.sleep(2)
                        retry_count += 1
                        continue

                    # 执行刷入命令
                    result = subprocess.run([self.get_fastboot_path(), "flash", partition, image_path],
                                            capture_output=True, text=True, encoding='utf-8', errors='ignore',
                                            timeout=300)
                    if result.returncode == 0:
                        return True
                    else:
                        error_msg = result.stderr.strip() or result.stdout.strip() or "刷入失败"
                        error_log.append(f"第{retry_count + 1}次刷入失败: {error_msg}")
                        time.sleep(2)
                        retry_count += 1
                except Exception as e:
                    error_log.append(f"刷入异常: {str(e)}")
                    time.sleep(2)
                    retry_count += 1

            self.last_error = "; ".join(error_log)
            return False
        except Exception as e:
            self.last_error = str(e)
            return False