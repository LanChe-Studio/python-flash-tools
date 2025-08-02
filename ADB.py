import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile

from PySide6.QtCore import QSettings


class ADB:
    """ADB工具管理类"""

    def __init__(self, host='127.0.0.1', port=5037):
        self.host = host
        self.port = port
        self.adb_path = None
        self.fastboot_path = None
        self.mtk_path = None
        self.server_started = False
        self.last_error = ""
        self.temp_dir = None
        self.settings = QSettings("PythonFlashTools", "FlashTool")
        self._init_adb()
        self._init_fastboot()
        self._init_mtkclient()

    def _get_platform_specific_name(self, tool):
        """获取平台特定的可执行文件名"""
        return f"{tool}.exe" if platform.system().lower() == "windows" else tool

    def _find_tool(self, tool_name, version_cmd, common_paths):
        """通用工具查找方法"""
        # 首先检查用户自定义路径
        custom_path = self.settings.value(f"{tool_name}_path", "")
        if custom_path and os.path.exists(custom_path):
            try:
                result = subprocess.run([custom_path, version_cmd],
                                        capture_output=True, text=True,
                                        encoding='utf-8', errors='ignore',
                                        timeout=2)
                if result.returncode == 0:
                    return custom_path
            except:
                pass

        # 查找系统PATH中的工具
        tool_exec = self._get_platform_specific_name(tool_name)
        try:
            result = subprocess.run([tool_exec, version_cmd],
                                    capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore',
                                    timeout=2)
            if result.returncode == 0:
                return tool_exec
        except:
            pass

        # 查找常见路径中的工具
        for path in common_paths:
            if not os.path.exists(path):
                continue
            try:
                result = subprocess.run([path, version_cmd],
                                        capture_output=True, text=True,
                                        encoding='utf-8', errors='ignore',
                                        timeout=2)
            except:
                continue

        return None

    def _init_adb(self):
        """初始化ADB"""
        common_paths = [
            "/usr/bin/adb",
            "/usr/local/bin/adb",
            os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", "adb"),
            os.path.join(os.environ.get("ANDROID_SDK_ROOT", ""), "platform-tools", "adb"),
            "C:\\Program Files (x86)\\Android\\android-sdk\\platform-tools\\adb.exe",
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
        ]

        self.adb_path = self._find_tool("adb", "version", common_paths)

        # 如果未找到，尝试下载
        if not self.adb_path:
            self.adb_path = self._download_adb()

    def _init_fastboot(self):
        """初始化Fastboot"""
        common_paths = [
            "/usr/bin/fastboot",
            "/usr/local/bin/fastboot",
            os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", "fastboot"),
            os.path.join(os.environ.get("ANDROID_SDK_ROOT", ""), "platform-tools", "fastboot"),
            "C:\\Program Files (x86)\\Android\\android-sdk\\platform-tools\\fastboot.exe",
            os.path.expanduser("~/Library/Android/sdk/platform-tools/fastboot")
        ]

        self.fastboot_path = self._find_tool("fastboot", "--version", common_paths)

        # 如果未找到，尝试下载
        if not self.fastboot_path:
            self.fastboot_path = self._download_fastboot()

    def _init_mtkclient(self):
        """初始化MTKClient"""
        # 首先检查用户自定义路径
        custom_path = self.settings.value("mtk_path", "")
        if custom_path and os.path.exists(custom_path):
            self.mtk_path = custom_path
            return

        # 查找常见路径中的MTKClient
        paths = [
            "mtk.py",
            os.path.expanduser("~/mtkclient/mtk.py"),
            "C:\\mtkclient\\mtk.py",
            os.path.expanduser("~/mtkclient/mtkclient/mtk.py"),
            "C:\\mtkclient\\mtkclient\\mtk.py"
        ]

        for path in paths:
            if os.path.exists(path):
                self.mtk_path = path
                return

        # 尝试下载
        self.mtk_path = self._download_mtkclient()

        # 不自动下载，等待用户操作
        self.mtk_path = None

    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"清理临时目录失败: {str(e)}")

    def _download_adb(self):
        """下载ADB工具"""
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]

        return self._download_tool("adb", mirrors)

    def _download_fastboot(self):
        """下载Fastboot工具"""
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]

        return self._download_tool("fastboot", mirrors)

    def _download_mtkclient(self):
        """下载MTKClient工具"""
        mirrors = [
            "https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip",
            "https://ghproxy.com/https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip"
        ]

        return self._download_tool("mtk", mirrors)

    def _download_tool(self, tool_name, mirrors):
        """通用工具下载方法"""
        try:
            # 创建永久工具目录
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            tool_dir = os.path.join(app_dir, "tools", tool_name)
            os.makedirs(tool_dir, exist_ok=True)

            zip_path = os.path.join(tool_dir, f"{tool_name}.zip")
            downloaded = False

            for mirror in mirrors:
                try:
                    urllib.request.urlretrieve(mirror, zip_path)
                    downloaded = True
                    break
                except Exception as e:
                    continue

            if not downloaded:
                return None

            # 解压文件
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tool_dir)
            except zipfile.BadZipFile:
                try:
                    with tarfile.open(zip_path, 'r:*') as tar_ref:
                        tar_ref.extractall(tool_dir)
                except Exception as e:
                    return None

            # 删除ZIP文件
            try:
                os.remove(zip_path)
            except:
                pass

            # 查找工具
            tool_path = None
            for root, dirs, files in os.walk(tool_dir):
                for file in files:
                    if tool_name == "mtk":
                        if file.lower() == "mtk.py":
                            tool_path = os.path.join(root, file)
                    else:
                        if file.lower().startswith(tool_name) and not file.endswith('.zip'):
                            tool_path = os.path.join(root, file)

                    if tool_path:
                        # 设置权限(非Windows)
                        if platform.system().lower() != "windows":
                            os.chmod(tool_path, 0o755)
                        break
                if tool_path:
                    break

            return tool_path
        except Exception as e:
            return None

    def _ensure_adb_server(self):
        """确保ADB服务器运行"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False

        try:
            # 先杀死可能存在的旧服务器进程
            subprocess.run([self.adb_path, "kill-server"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           timeout=5)

            # 启动新服务器
            subprocess.run([self.adb_path, "start-server"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           timeout=10)
            self.server_started = True

            # 等待服务器完全启动
            time.sleep(2)
            return True
        except Exception as e:
            self.last_error = f"启动ADB服务失败: {str(e)}"
            return False

    def devices(self):
        """获取设备列表"""
        if not self._ensure_adb_server():
            return []

        try:
            result = subprocess.run([self.adb_path, "devices"],
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

    def fastboot_devices(self):
        """获取fastboot设备列表"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return []

        try:
            result = subprocess.run([self.fastboot_path, "devices"],
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

    def detect_mtk_devices(self):
        """检测MTK设备 - 增强版"""
        if not self.mtk_path:
            self.last_error = "MTKClient工具未找到"
            return []

        try:
            # 使用更长的超时时间，因为检测可能需要一些时间
            result = subprocess.run([sys.executable, self.mtk_path, "detect"],
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

    def reboot(self, mode=None):
        """重启设备"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False, "ADB工具未找到"

        cmd = [self.adb_path, "reboot"]
        if mode in ["bootloader", "recovery"]:
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
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False, "Fastboot工具未找到"

        try:
            result = subprocess.run([self.fastboot_path, "reboot"],
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

    def backup_partition(self, partition, output_path):
        """备份分区"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return False

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cmd = f"su -c 'dd if=/dev/block/bootdevice/by-name/{partition} of={output_path}'"
            result = subprocess.run([self.adb_path, "shell", cmd],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    timeout=300,
                                    encoding='utf-8',
                                    errors='ignore')

            # 检查授权问题
            output = result.stdout + result.stderr
            if "unauthorized" in output or "device unauthorized" in output:
                self.last_error = "设备未授权，请检查设备屏幕并确认授权"
                return False

            return result.returncode == 0
        except Exception as e:
            self.last_error = str(e)
            return False

    def execute_adb_command(self, command):
        """执行ADB命令"""
        if not self.adb_path:
            self.last_error = "ADB工具未找到"
            return None

        try:
            result = subprocess.run([self.adb_path] + command.split(),
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
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return None

        try:
            result = subprocess.run([self.fastboot_path] + command.split(),
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

    def unlock_bootloader(self):
        """解锁Bootloader"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False, "Fastboot工具未找到"

        try:
            result = subprocess.run([self.fastboot_path, "flashing", "unlock"],
                                    capture_output=True,
                                    text=True,
                                    timeout=60,
                                    encoding='utf-8',
                                    errors='ignore')
            if result.returncode != 0:
                result = subprocess.run([self.fastboot_path, "oem", "unlock"],
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
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False, "Fastboot工具未找到"

        try:
            result = subprocess.run([self.fastboot_path, "flashing", "lock"],
                                    capture_output=True,
                                    text=True,
                                    timeout=60,
                                    encoding='utf-8',
                                    errors='ignore')
            if result.returncode != 0:
                result = subprocess.run([self.fastboot_path, "oem", "lock"],
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

    def backup_partition_fastboot(self, partition, output_path):
        """使用Fastboot备份分区"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False

        try:
            # 获取分区大小
            result = subprocess.run([self.fastboot_path, "getvar", f"partition-size:{partition}"],
                                    capture_output=True, text=True, encoding='utf-8', errors='ignore',
                                    timeout=60)
            if result.returncode != 0:
                self.last_error = f"无法获取分区大小: {result.stderr or '未知错误'}"
                return False

            # 解析分区大小
            size_line = [line for line in result.stdout.splitlines() if "partition-size" in line]
            if not size_line:
                self.last_error = "无法解析分区大小"
                return False

            size_str = size_line[0].split(":")[1].strip()
            if not size_str.isdigit():
                self.last_error = f"无效的分区大小: {size_str}"
                return False

            partition_size = int(size_str)

            # 备份分区
            with open(output_path, 'wb') as f:
                result = subprocess.run([self.fastboot_path, "fetch", f"{partition}"],
                                        stdout=f, stderr=subprocess.PIPE,
                                        timeout=300)

            if result.returncode == 0:
                actual_size = os.path.getsize(output_path)
                if actual_size == partition_size:
                    return True
                else:
                    self.last_error = f"备份文件大小不匹配: 预期 {partition_size} 字节, 实际 {actual_size} 字节"
                    return False
            else:
                self.last_error = result.stderr.decode('utf-8', 'ignore') if result.stderr else "未知错误"
                return False
        except Exception as e:
            self.last_error = str(e)
            return False

    def flash_partition(self, partition, image_path):
        """刷入分区"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False

        try:
            # 增加重试机制
            max_retries = 5
            retry_count = 0
            success = False
            error_log = []

            while not success and retry_count < max_retries:
                try:
                    # 检查设备连接
                    devices = self.fastboot_devices()
                    if not devices:
                        error_log.append(f"第{retry_count + 1}次重试: 未检测到Fastboot设备")
                        time.sleep(2)
                        retry_count += 1
                        continue

                    # 执行刷入命令
                    result = subprocess.run([self.fastboot_path, "flash", partition, image_path],
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

    def flash_all_partitions(self, images_dir):
        """刷入所有分区"""
        if not self.fastboot_path:
            self.last_error = "Fastboot工具未找到"
            return False

        try:
            result = subprocess.run([self.fastboot_path, "flashall"],
                                    cwd=images_dir,
                                    capture_output=True, text=True, encoding='utf-8', errors='ignore',
                                    timeout=600)
            return result.returncode == 0
        except Exception as e:
            self.last_error = str(e)
            return False

    def execute_mtk_command(self, command_args):
        """执行MTKClient命令 - 使用参数列表而不是字符串"""
        if not self.mtk_path:
            self.last_error = "MTKClient工具未找到"
            return None

        try:
            # 构建命令列表
            cmd = [sys.executable, self.mtk_path] + command_args

            result = subprocess.run(cmd,
                                    capture_output=True,
                                    text=True,
                                    timeout=120,
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
