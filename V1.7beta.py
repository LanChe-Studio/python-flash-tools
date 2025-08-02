import os
import sys
import time
import threading
import subprocess
import platform
import tempfile
import urllib.request
import zipfile
import shutil
import tarfile
import re
import logging
import queue
import webbrowser
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import tkinter.font as tkfont

class DownloadDialog(tk.Toplevel):
    """依赖下载对话框"""
    def __init__(self, parent, tools):
        super().__init__(parent)
        self.title("依赖未安装")
        self.geometry("500x300")
        self.tools = tools
        self.tool_paths = {}
        
        # 设置窗口居中
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        # 提示信息
        label = ttk.Label(self, text=f"以下工具缺失: {', '.join(tools)}\n是否现在下载?",
                         wraplength=480, justify="center", font=("Arial", 12))
        label.pack(pady=10, padx=10)
        
        # 进度条
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var, 
                                          maximum=100, length=450)
        self.progress_bar.pack(pady=5, padx=10)
        self.progress_bar.pack_forget()  # 初始隐藏
        
        # 日志输出
        self.log_output = scrolledtext.ScrolledText(self, width=60, height=8,
                                                  font=("Consolas", 9))
        self.log_output.pack(pady=5, padx=10)
        self.log_output.pack_forget()  # 初始隐藏
        
        # 按钮布局
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10, padx=10, fill=tk.X)
        
        self.later_btn = ttk.Button(btn_frame, text="稍后设置", 
                                  command=self.on_later)
        self.later_btn.pack(side=tk.RIGHT, padx=5)
        
        self.download_btn = ttk.Button(btn_frame, text="现在下载", 
                                     command=self.start_download)
        self.download_btn.pack(side=tk.RIGHT, padx=5)
        
        ttk.Label(btn_frame).pack(side=tk.RIGHT, expand=True)  # 占位符
        
        self.protocol("WM_DELETE_WINDOW", self.on_later)
        self.grab_set()
    
    def on_later(self):
        """稍后设置"""
        self.destroy()
    
    def start_download(self):
        """开始下载依赖"""
        self.download_btn.config(state=tk.DISABLED)
        self.later_btn.config(state=tk.DISABLED)
        self.progress_bar.pack(pady=5, padx=10)
        self.log_output.pack(pady=5, padx=10)
        
        # 启动下载线程
        threading.Thread(target=self.download_tools, daemon=True).start()
    
    def download_tools(self):
        """下载工具"""
        self.log("开始下载缺失的工具...")
        self.progress_var.set(0)
        
        tool_count = len(self.tools)
        downloaded_count = 0
        
        for tool in self.tools:
            if tool == "ADB":
                self.log("下载ADB工具...")
                tool_path = self.download_adb()
                if tool_path:
                    self.tool_paths["adb"] = tool_path
                    self.log(f"ADB下载成功: {tool_path}")
                    downloaded_count += 1
                else:
                    self.log("ADB下载失败")
            elif tool == "Fastboot":
                self.log("下载Fastboot工具...")
                tool_path = self.download_fastboot()
                if tool_path:
                    self.tool_paths["fastboot"] = tool_path
                    self.log(f"Fastboot下载成功: {tool_path}")
                    downloaded_count += 1
                else:
                    self.log("Fastboot下载失败")
            elif tool == "MTKClient":
                self.log("下载MTKClient工具...")
                tool_path = self.download_mtkclient()
                if tool_path:
                    self.tool_paths["mtk"] = tool_path
                    self.log(f"MTKClient下载成功: {tool_path}")
                    downloaded_count += 1
                else:
                    self.log("MTKClient下载失败")
            
            # 更新进度
            progress = int(downloaded_count / tool_count * 100)
            self.progress_var.set(progress)
        
        if downloaded_count == tool_count:
            self.log("所有工具下载完成!")
            self.destroy()
        else:
            self.log(f"部分工具下载失败 ({downloaded_count}/{tool_count})")
            self.download_btn.config(state=tk.NORMAL)
            self.later_btn.config(state=tk.NORMAL)
    
    def download_adb(self):
        """下载ADB工具"""
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]
        
        return self.download_tool("adb", mirrors)
    
    def download_fastboot(self):
        """下载Fastboot工具"""
        system = platform.system().lower()
        mirrors = [
            f"https://dl.google.com/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.bfsu.edu.cn/android/repository/platform-tools-latest-{system}.zip",
            f"https://mirrors.tuna.tsinghua.edu.cn/github-release/android/platform-tools/LatestRelease/platform-tools-latest-{system}.zip"
        ]
        
        return self.download_tool("fastboot", mirrors)
    
    def download_mtkclient(self):
        """下载MTKClient工具"""
        mirrors = [
            "https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip",
            "https://ghproxy.com/https://github.com/bkerler/mtkclient/archive/refs/heads/main.zip"
        ]
        
        return self.download_tool("mtk", mirrors)
    
    def download_tool(self, tool_name, mirrors):
        """通用工具下载方法"""
        try:
            # 创建永久工具目录
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            tool_dir = os.path.join(app_dir, "tools", tool_name)
            os.makedirs(tool_dir, exist_ok=True)
            
            zip_path = os.path.join(tool_dir, f"{tool_name}.zip")
            downloaded = False
            
            # 下载进度回调
            def report_progress(count, block_size, total_size):
                if total_size > 0:
                    percent = min(100, int(count * block_size * 100 / total_size))
                    self.progress_var.set(percent)
            
            for mirror in mirrors:
                try:
                    self.log(f"尝试从 {mirror} 下载...")
                    urllib.request.urlretrieve(mirror, zip_path, report_progress)
                    downloaded = True
                    self.log(f"{tool_name} 下载完成")
                    break
                except Exception as e:
                    self.log(f"下载失败: {str(e)}")
                    continue
            
            if not downloaded:
                self.log("所有镜像源下载失败")
                return None
            
            # 解压文件
            try:
                self.log("解压文件...")
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tool_dir)
            except zipfile.BadZipFile:
                try:
                    with tarfile.open(zip_path, 'r:*') as tar_ref:
                        tar_ref.extractall(tool_dir)
                except Exception as e:
                    self.log(f"解压失败: {str(e)}")
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
                        self.log(f"找到工具: {tool_path}")
                        break
                if tool_path:
                    break
            
            if not tool_path:
                self.log(f"解压后未找到{tool_name}主文件")
                return None
            
            return tool_path
        except Exception as e:
            self.log(f"下载{tool_name}失败: {str(e)}")
            return None
    
    def log(self, message):
        """记录日志"""
        self.log_output.insert(tk.END, message + "\n")
        self.log_output.see(tk.END)

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
        self.app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))  # 获取应用目录
        self._init_adb()
        self._init_fastboot()
        self._init_mtkclient()

    def _get_platform_specific_name(self, tool):
        """获取平台特定的可执行文件名"""
        return f"{tool}.exe" if platform.system().lower() == "windows" else tool

    def _find_tool(self, tool_name, version_cmd, common_paths):
        """通用工具查找方法"""
        # 首先检查用户自定义路径
        custom_path = ""
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
                if result.returncode == 0:
                    return path
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
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
            os.path.join(self.app_dir, "tools", "adb", "platform-tools", self._get_platform_specific_name("adb")),
            os.path.join(self.app_dir, "tools", "adb", self._get_platform_specific_name("adb"))
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
            os.path.expanduser("~/Library/Android/sdk/platform-tools/fastboot"),
            os.path.join(self.app_dir, "tools", "fastboot", "platform-tools", self._get_platform_specific_name("fastboot")),
            os.path.join(self.app_dir, "tools", "fastboot", self._get_platform_specific_name("fastboot"))
        ]
        
        self.fastboot_path = self._find_tool("fastboot", "--version", common_paths)
        
        # 如果未找到，尝试下载
        if not self.fastboot_path:
            self.fastboot_path = self._download_fastboot()
    
    def _init_mtkclient(self):
        """初始化MTKClient"""
        # 查找常见路径中的MTKClient
        paths = [
            "mtk.py",
            os.path.expanduser("~/mtkclient/mtk.py"),
            "C:\\mtkclient\\mtk.py",
            os.path.expanduser("~/mtkclient/mtkclient/mtk.py"),
            "C:\\mtkclient\\mtkclient\\mtk.py",
            os.path.join(self.app_dir, "tools", "mtk", "mtk.py"),
            os.path.join(self.app_dir, "tools", "mtk", "mtkclient", "mtk.py")
        ]
        
        for path in paths:
            if os.path.exists(path):
                self.mtk_path = path
                return
        
        # 尝试下载
        self.mtk_path = self._download_mtkclient()
        if not self.mtk_path:
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
            tool_dir = os.path.join(self.app_dir, "tools", tool_name)
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
                        error_log.append(f"第{retry_count+1}次重试: 未检测到Fastboot设备")
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
                        error_log.append(f"第{retry_count+1}次刷入失败: {error_msg}")
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

class SettingDialog(tk.Toplevel):
    """设置对话框"""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.title("设置")
        self.geometry("500x400")
        self.app = app
        self.app_config = app.app_config  # 使用app_config属性
        self.theme_var = tk.StringVar(value=self.app_config.get("theme", "light"))
        
        # 设置窗口居中
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        # 创建笔记本控件
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 工具路径设置标签页
        self.tool_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tool_frame, text="工具路径")
        self._create_tool_settings()
        
        # 主题设置标签页
        self.theme_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.theme_frame, text="主题设置")
        self._create_theme_settings()
        
        # 按钮区域
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="保存", command=self.save_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()
    
    def _create_tool_settings(self):
        """创建工具路径设置界面"""
        # ADB路径设置
        adb_frame = ttk.LabelFrame(self.tool_frame, text="ADB路径")
        adb_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.adb_path_var = tk.StringVar(value=self.app_config.get("adb_path", ""))
        ttk.Entry(adb_frame, textvariable=self.adb_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(adb_frame, text="浏览", command=lambda: self.select_path(self.adb_path_var)).pack(side=tk.RIGHT, padx=5)
        
        # Fastboot路径设置
        fastboot_frame = ttk.LabelFrame(self.tool_frame, text="Fastboot路径")
        fastboot_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.fastboot_path_var = tk.StringVar(value=self.app_config.get("fastboot_path", ""))
        ttk.Entry(fastboot_frame, textvariable=self.fastboot_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(fastboot_frame, text="浏览", command=lambda: self.select_path(self.fastboot_path_var)).pack(side=tk.RIGHT, padx=5)
        
        # MTKClient路径设置
        mtk_frame = ttk.LabelFrame(self.tool_frame, text="MTKClient路径")
        mtk_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.mtk_path_var = tk.StringVar(value=self.app_config.get("mtk_path", ""))
        ttk.Entry(mtk_frame, textvariable=self.mtk_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        ttk.Button(mtk_frame, text="浏览", command=lambda: self.select_path(self.mtk_path_var)).pack(side=tk.RIGHT, padx=5)
        
        # 恢复默认值
        ttk.Button(self.tool_frame, text="恢复默认路径", command=self.reset_to_default).pack(pady=10)
    
    def _create_theme_settings(self):
        """创建主题设置界面"""
        # 主题选择
        theme_frame = ttk.LabelFrame(self.theme_frame, text="主题设置")
        theme_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Radiobutton(theme_frame, text="浅色主题", variable=self.theme_var, value="light").pack(anchor=tk.W, padx=5, pady=5)
        ttk.Radiobutton(theme_frame, text="深色主题", variable=self.theme_var, value="dark").pack(anchor=tk.W, padx=5, pady=5)
        
        # 主题预览
        preview_frame = ttk.LabelFrame(self.theme_frame, text="主题预览")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        preview_text = tk.Text(preview_frame, height=8, wrap=tk.WORD)
        preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        preview_text.insert(tk.END, "这是一个主题预览示例\n浅色主题适合白天使用\n深色主题适合夜间使用")
        preview_text.config(state=tk.DISABLED)
        
        # 应用主题按钮
        ttk.Button(self.theme_frame, text="应用主题", command=self.apply_theme).pack(pady=10)
    
    def select_path(self, path_var):
        """选择路径"""
        path = filedialog.askopenfilename(title="选择文件")
        if path:
            path_var.set(path)
    
    def reset_to_default(self):
        """恢复默认路径"""
        self.adb_path_var.set("")
        self.fastboot_path_var.set("")
        self.mtk_path_var.set("")
    
    def apply_theme(self):
        """应用主题"""
        theme = self.theme_var.get()
        self.app.apply_theme(theme)
    
    def save_settings(self):
        """保存设置"""
        # 保存工具路径
        self.app_config["adb_path"] = self.adb_path_var.get()
        self.app_config["fastboot_path"] = self.fastboot_path_var.get()
        self.app_config["mtk_path"] = self.mtk_path_var.get()
        
        # 保存主题设置
        self.app_config["theme"] = self.theme_var.get()
        
        # 保存配置文件
        self.app.save_config()
        
        # 重新初始化工具
        self.app.reinitialize_tools()
        
        messagebox.showinfo("设置", "设置已保存并生效")
        self.destroy()

class LogViewer(tk.Toplevel):
    """日志查看器"""
    def __init__(self, parent, log_queue):
        super().__init__(parent)
        self.title("调试日志")
        self.geometry("800x600")
        self.log_queue = log_queue
        
        # 设置窗口居中
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        # 创建工具栏
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="清除日志", command=self.clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="保存日志", command=self.save_log).pack(side=tk.LEFT, padx=5)
        
        # 创建日志显示区域
        self.log_text = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text.config(state=tk.DISABLED)
        
        # 启动日志更新线程
        self.running = True
        threading.Thread(target=self.update_log, daemon=True).start()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def clear_log(self):
        """清除日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def save_log(self):
        """保存日志到文件"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("日志文件", "*.log"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("保存成功", f"日志已保存到:\n{file_path}")
            except Exception as e:
                messagebox.showerror("保存失败", f"保存日志失败: {str(e)}")
    
    def update_log(self):
        """更新日志显示"""
        while self.running:
            try:
                while not self.log_queue.empty():
                    log_entry = self.log_queue.get_nowait()
                    self.log_text.config(state=tk.NORMAL)
                    self.log_text.insert(tk.END, log_entry + "\n")
                    self.log_text.see(tk.END)
                    self.log_text.config(state=tk.DISABLED)
            except:
                pass
            time.sleep(0.1)
    
    def on_close(self):
        """关闭窗口"""
        self.running = False
        self.destroy()

class AboutDialog(tk.Toplevel):
    """关于对话框"""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("关于 Python Flash Tools")
        self.geometry("600x450")
        
        # 设置窗口居中
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'+{x}+{y}')
        
        # 创建文本控件
        about_text = tk.Text(self, wrap=tk.WORD, padx=20, pady=20)
        about_text.pack(fill=tk.BOTH, expand=True)
        
        # 插入关于信息
        about_text.insert(tk.END, "Python Flash Tools V1.7 Beta\n", "title")
        about_text.insert(tk.END, "Powered by LanChe-Studio\n\n", "subtitle")
        about_text.insert(tk.END, "开源项目\n", "header")
        about_text.insert(tk.END, "https://github.com/LanChe-Studio/python-flash-tools\n")
        about_text.insert(tk.END, "开源协议: GPL 3.0\n\n", "normal")
        about_text.insert(tk.END, "使用的组件:\n", "header")
        about_text.insert(tk.END, "MTKClient: https://github.com/bkerler/mtkclient (GPL 3.0)\n")
        about_text.insert(tk.END, "Android SDK: https://github.com/aosp-mirror\n")
        about_text.insert(tk.END, "Python: https://www.python.org/ (Python Software Foundation License)\n\n", "normal")
        about_text.insert(tk.END, "Copyright © 2023-2025 LanChe-Studio. 保留所有权利。\n", "normal")
        about_text.insert(tk.END, "本软件按原样提供，不提供任何明示或暗示的担保。\n", "normal")
        
        # 配置标签样式
        about_text.tag_configure("title", font=("Arial", 16, "bold"), justify="center")
        about_text.tag_configure("subtitle", font=("Arial", 12), justify="center")
        about_text.tag_configure("header", font=("Arial", 10, "bold"))
        about_text.tag_configure("normal", font=("Arial", 9))
        
        # 设置为只读
        about_text.config(state=tk.DISABLED)
        
        # 确定按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Button(btn_frame, text="确定", command=self.destroy).pack(side=tk.RIGHT)
    
    def open_link(self, url):
        """打开链接"""
        webbrowser.open(url)

class FlashTool(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Python Flash Tools V1.7 Beta")
        self.geometry("800x600")
        
        # 初始化配置
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flash_tools_config.json")
        self.app_config = self.load_config()  # 重命名为 app_config
        
        # 初始化日志
        self.log_queue = queue.Queue()
        self.setup_logging()
        
        # 初始化变量
        self.current_mode = None
        self.device_id = None
        self.adb = ADB()
        self.firmware_path = ""
        self.backup_path = ""
        self.operation_in_progress = False
        self.running = True  # 设备检测线程运行标志
        self.mtk_detecting = False  # MTK设备检测标志
        self.xiaomi_flash_path = ""
        self.bootrom_flash_path = ""
        self.partition_img_path = ""
        self.mtk_process = None  # 存储当前运行的MTKClient进程
        self._last_update_time = time.time()
        
        # 创建主界面
        self._init_ui()
        
        # 启动设备检测线程
        self._start_device_check()
        
        # 检查工具依赖
        self._check_tools()
        
        # 应用主题
        self.apply_theme(self.app_config.get("theme", "light"))
    
    def load_config(self):
        """加载配置文件"""
        config = {
            "adb_path": "",
            "fastboot_path": "",
            "mtk_path": "",
            "theme": "light"
        }
        
        try:
            if os.path.exists(self.config_file):
                import json
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    # 只更新存在的键
                    for key in config:
                        if key in loaded_config:
                            config[key] = loaded_config[key]
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
        
        return config
    
    def save_config(self):
        """保存配置文件"""
        try:
            import json
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.app_config, f, indent=4)
        except Exception as e:
            logging.error(f"保存配置文件失败: {str(e)}")
    
    def setup_logging(self):
        """配置日志系统"""
        # 创建日志目录
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # 日志文件路径
        log_file = os.path.join(log_dir, f"flash_tools_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        
        # 创建UI日志处理器（将日志放入队列）
        class UIHandler(logging.Handler):
            def __init__(self, log_queue):
                super().__init__()
                self.log_queue = log_queue
                
            def emit(self, record):
                log_entry = self.format(record)
                try:
                    self.log_queue.put(log_entry)
                except Exception:
                    pass  # 防止队列阻塞导致程序崩溃
        
        ui_handler = UIHandler(self.log_queue)
        ui_handler.setLevel(logging.DEBUG)
        ui_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        ui_handler.setFormatter(ui_formatter)
        
        # 添加处理器到根日志记录器
        root_logger.addHandler(file_handler)
        root_logger.addHandler(ui_handler)
        
        logging.info("日志系统初始化完成")
    
    def apply_theme(self, theme):
        """应用主题"""
        if theme == "dark":
            # 深色主题
            bg_color = "#2d2d2d"
            fg_color = "#e0e0e0"
            entry_bg = "#3d3d3d"
            button_bg = "#4d4d4d"
            highlight_color = "#3a7ebf"
            self.style.theme_use("clam")
            self.app_config["theme"] = "dark"
        else:  # light theme
            # 浅色主题
            bg_color = "#f5f5f5"
            fg_color = "#333333"
            entry_bg = "#ffffff"
            button_bg = "#e0e0e0"
            highlight_color = "#4a86e8"
            self.style.theme_use("clam")
            self.app_config["theme"] = "light"
        
        # 应用颜色方案
        self.configure(bg=bg_color)
        
        # 配置样式
        self.style.configure(".", background=bg_color, foreground=fg_color, font=("Arial", 10))
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=fg_color)
        self.style.configure("TButton", background=button_bg, foreground=fg_color, 
                            borderwidth=1, relief="raised", padding=5)
        self.style.configure("TEntry", fieldbackground=entry_bg, foreground=fg_color, 
                            insertbackground=fg_color)
        self.style.configure("TCombobox", fieldbackground=entry_bg, foreground=fg_color)
        self.style.configure("TNotebook", background=bg_color)
        self.style.configure("TNotebook.Tab", background=bg_color, foreground=fg_color, 
                            padding=[10, 5])
        self.style.configure("TScrollbar", background=button_bg, troughcolor=bg_color)
        self.style.configure("Treeview", background=entry_bg, fieldbackground=entry_bg, 
                            foreground=fg_color)
        self.style.configure("Treeview.Heading", background=button_bg, foreground=fg_color)
        self.style.configure("TLabelframe", background=bg_color, foreground=highlight_color)
        self.style.configure("TLabelframe.Label", background=bg_color, foreground=highlight_color)
        
        # 高亮按钮样式
        self.style.map("TButton",
                      background=[('active', highlight_color), ('pressed', highlight_color)],
                      foreground=[('active', '#ffffff'), ('pressed', '#ffffff')])
        
        # 保存主题设置
        self.save_config()
        logging.info(f"应用{theme}主题")
    
    def reinitialize_tools(self):
        """重新初始化工具"""
        self.adb = ADB()
        self._update_tool_status()
        logging.info("工具已重新初始化")
    
    def _check_tools(self):
        """检查工具依赖"""
        missing_tools = []
        if not self.adb.adb_path:
            missing_tools.append("ADB")
        if not self.adb.fastboot_path:
            missing_tools.append("Fastboot")
        if not self.adb.mtk_path:
            missing_tools.append("MTKClient")
        
        if missing_tools:
            self._show_download_dialog(missing_tools)
    
    def _show_download_dialog(self, tools):
        """显示下载对话框"""
        dialog = DownloadDialog(self, tools)
        self.wait_window(dialog)
        
        # 重新初始化ADB以应用新的路径设置
        self.adb = ADB()
        # 更新工具状态显示
        self._update_tool_status()
    
    def _update_tool_status(self):
        """更新工具状态标签"""
        self.adb_status.config(text=f"ADB: {'可用' if self.adb.adb_path else '不可用'}")
        self.fastboot_status.config(text=f"Fastboot: {'可用' if self.adb.fastboot_path else '不可用'}")
        self.mtk_status.config(text=f"MTKClient: {'可用' if self.adb.mtk_path else '不可用'}")
    
    def _init_ui(self):
        """初始化用户界面"""
        # 创建菜单栏
        self._create_menu()
        
        # 创建标签页
        self.style = ttk.Style(self)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 设备标签页
        self.device_tab = self._create_device_tab()
        self.notebook.add(self.device_tab, text="设备")
        
        # 刷机标签页
        self.flash_tab = self._create_flash_tab()
        self.notebook.add(self.flash_tab, text="刷机")
        
        # 备份标签页
        self.backup_tab = self._create_backup_tab()
        self.notebook.add(self.backup_tab, text="备份")
        
        # ADB命令标签页
        self.adb_tab = self._create_adb_tab()
        self.notebook.add(self.adb_tab, text="ADB命令")
        
        # Fastboot命令标签页
        self.fastboot_tab = self._create_fastboot_tab()
        self.notebook.add(self.fastboot_tab, text="Fastboot命令")
        
        # BL解锁标签页
        self.unlock_tab = self._create_unlock_tab()
        self.notebook.add(self.unlock_tab, text="BL解锁")
        
        # 小米线刷标签页
        self.xiaomi_tab = self._create_xiaomi_tab()
        self.notebook.add(self.xiaomi_tab, text="小米线刷")
        
        # MTK工具标签页
        self.mtk_tab = self._create_mtk_tab()
        self.notebook.add(self.mtk_tab, text="MTK工具")
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _create_menu(self):
        """创建菜单栏"""
        menu_bar = tk.Menu(self)
        
        # 文件菜单
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="退出", command=self.on_closing)
        menu_bar.add_cascade(label="文件", menu=file_menu)
        
        # 工具菜单
        tools_menu = tk.Menu(menu_bar, tearoff=0)
        tools_menu.add_command(label="设置", command=self.open_settings)
        tools_menu.add_command(label="查看调试日志", command=self.open_log_viewer)
        menu_bar.add_cascade(label="工具", menu=tools_menu)
        
        # 帮助菜单
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menu_bar.add_cascade(label="帮助", menu=help_menu)
        
        self.config(menu=menu_bar)  # 使用Tk的config方法设置菜单
    
    def open_settings(self):
        """打开设置对话框"""
        SettingDialog(self, self)
    
    def open_log_viewer(self):
        """打开日志查看器"""
        LogViewer(self, self.log_queue)
    
    def _show_about(self):
        """显示关于信息"""
        AboutDialog(self)
    
    def _create_device_tab(self):
        """创建设备标签页"""
        tab = ttk.Frame(self.notebook)
        
        # 设备状态
        status_frame = ttk.LabelFrame(tab, text="设备状态")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.device_status = ttk.Label(status_frame, text="等待设备连接...", font=("Arial", 12))
        self.device_status.pack(pady=5, padx=10, anchor=tk.W)
        
        self.device_info = ttk.Label(status_frame, text="", font=("Arial", 10))
        self.device_info.pack(pady=5, padx=10, anchor=tk.W)
        
        # 设备详细信息
        details_frame = ttk.LabelFrame(tab, text="设备信息")
        details_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.device_details = ttk.Label(details_frame, text="设备详细信息将在此显示", font=("Arial", 9))
        self.device_details.pack(pady=5, padx=10, anchor=tk.W)
        
        # 操作按钮
        btn_frame = ttk.LabelFrame(tab, text="设备操作")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        btn_grid = ttk.Frame(btn_frame)
        btn_grid.pack(padx=10, pady=5)
        
        self.bootloader_btn = ttk.Button(btn_grid, text="进入Bootloader", command=self._enter_bootloader)
        self.bootloader_btn.grid(row=0, column=0, padx=5, pady=5)
        
        self.recovery_btn = ttk.Button(btn_grid, text="进入Recovery", command=self._enter_recovery)
        self.recovery_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.reboot_btn = ttk.Button(btn_grid, text="重启设备", command=self._reboot_device)
        self.reboot_btn.grid(row=1, column=0, padx=5, pady=5)
        
        self.detect_mtk_btn = ttk.Button(btn_grid, text="检测MTK设备", command=self._detect_mtk_devices)
        self.detect_mtk_btn.grid(row=1, column=1, padx=5, pady=5)
        
        # 工具状态
        tools_frame = ttk.LabelFrame(tab, text="工具状态")
        tools_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.adb_status = ttk.Label(tools_frame, text="ADB: 检测中...")
        self.adb_status.pack(pady=2, padx=10, anchor=tk.W)
        
        self.fastboot_status = ttk.Label(tools_frame, text="Fastboot: 检测中...")
        self.fastboot_status.pack(pady=2, padx=10, anchor=tk.W)
        
        self.mtk_status = ttk.Label(tools_frame, text=f"MTKClient: {'可用' if self.adb.mtk_path else '不可用'}")
        self.mtk_status.pack(pady=2, padx=10, anchor=tk.W)
        
        return tab
    
    def _create_flash_tab(self):
        """创建刷机标签页"""
        tab = ttk.Frame(self.notebook)
        
        # 固件选择
        file_frame = ttk.LabelFrame(tab, text="固件选择")
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        file_select_frame = ttk.Frame(file_frame)
        file_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.file_label = ttk.Label(file_select_frame, text="未选择固件")
        self.file_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(file_select_frame, text="选择固件", command=self._select_firmware).pack(side=tk.RIGHT, padx=5)
        
        # 分区选择
        partition_frame = ttk.LabelFrame(tab, text="分区选择")
        partition_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.partition_combo = ttk.Combobox(partition_frame, values=["全部", "boot", "recovery", "system", "vendor", "userdata", "cache", "vbmeta"])
        self.partition_combo.current(0)
        self.partition_combo.pack(padx=10, pady=5, fill=tk.X)
        
        # 进度条
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(tab, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # 刷机按钮
        self.flash_btn = ttk.Button(tab, text="开始刷机", command=self._start_flashing)
        self.flash_btn.pack(padx=10, pady=10)
        
        # 支持格式说明
        format_label = ttk.Label(tab, text="支持格式: zip, img, bin, tgz, tar.gz", foreground="gray")
        format_label.pack(padx=10, pady=5)
        
        # USB连接提示
        usb_label = ttk.Label(tab, text="提示: 确保使用高质量USB数据线并连接到USB 2.0端口", foreground="orange")
        usb_label.pack(padx=10, pady=5)
        
        return tab
    
    def _create_backup_tab(self):
        """创建备份标签页"""
        tab = ttk.Frame(self.notebook)
        
        # 备份路径选择
        path_frame = ttk.LabelFrame(tab, text="备份路径")
        path_frame.pack(fill=tk.X, padx=10, pady=5)
        
        path_select_frame = ttk.Frame(path_frame)
        path_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.backup_path_label = ttk.Label(path_select_frame, text="未选择备份路径")
        self.backup_path_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(path_select_frame, text="选择路径", command=self._select_backup_path).pack(side=tk.RIGHT, padx=5)
        
        # 分区选择
        partition_frame = ttk.LabelFrame(tab, text="分区选择")
        partition_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.backup_partition_combo = ttk.Combobox(partition_frame, values=["boot", "recovery", "system", "vendor", "userdata", "cache"])
        self.backup_partition_combo.current(0)
        self.backup_partition_combo.pack(padx=10, pady=5, fill=tk.X)
        
        # 备份按钮
        self.backup_btn = ttk.Button(tab, text="开始备份", command=self._start_backup)
        self.backup_btn.pack(padx=10, pady=10)
        
        # 提示信息
        info_label = ttk.Label(tab, text="注意: 此备份功能使用Fastboot模式，需要设备处于Fastboot模式", foreground="gray")
        info_label.pack(padx=10, pady=5)
        
        # 空间提示
        space_label = ttk.Label(tab, text="确保目标驱动器有足够空间（系统分区通常需要2GB以上空间）", foreground="orange")
        space_label.pack(padx=10, pady=5)
        
        return tab
    
    def _create_adb_tab(self):
        """创建ADB命令标签页"""
        tab = ttk.Frame(self.notebook)
        
        # 命令输入
        input_frame = ttk.LabelFrame(tab, text="ADB命令")
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.adb_command_input = ttk.Entry(input_frame)
        self.adb_command_input.pack(fill=tk.X, padx=10, pady=5)
        self.adb_command_input.insert(0, "shell ls /sdcard")
        
        execute_btn = ttk.Button(input_frame, text="执行ADB命令", command=self._execute_adb_command)
        execute_btn.pack(padx=10, pady=5)
        
        # 输出显示
        output_frame = ttk.LabelFrame(tab, text="输出结果")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.adb_output = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD)
        self.adb_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 常用命令按钮
        common_frame = ttk.LabelFrame(tab, text="常用命令")
        common_frame.pack(fill=tk.X, padx=10, pady=5)
        
        common_commands = [
            ("设备信息", "shell getprop"),
            ("文件列表", "shell ls /sdcard"),
            ("截图", "shell screencap -p /sdcard/screenshot.png"),
            ("拉取文件", "pull /sdcard/screenshot.png"),
            ("推送文件", "push local.txt /sdcard/"),
            ("安装应用", "install app.apk")
        ]
        
        for i, (text, cmd) in enumerate(common_commands):
            btn = ttk.Button(common_frame, text=text, 
                           command=lambda c=cmd: self._set_adb_command(c))
            btn.grid(row=i//3, column=i%3, padx=5, pady=5, sticky=tk.W)
        
        return tab
    
    def _create_fastboot_tab(self):
        """创建Fastboot命令标签页"""
        tab = ttk.Frame(self.notebook)
        
        # 命令输入
        input_frame = ttk.LabelFrame(tab, text="Fastboot命令")
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.fastboot_command_input = ttk.Entry(input_frame)
        self.fastboot_command_input.pack(fill=tk.X, padx=10, pady=5)
        self.fastboot_command_input.insert(0, "devices")
        
        execute_btn = ttk.Button(input_frame, text="执行Fastboot命令", command=self._execute_fastboot_command)
        execute_btn.pack(padx=10, pady=5)
        
        # 输出显示
        output_frame = ttk.LabelFrame(tab, text="输出结果")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.fastboot_output = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD)
        self.fastboot_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 常用命令按钮
        common_frame = ttk.LabelFrame(tab, text="常用命令")
        common_frame.pack(fill=tk.X, padx=10, pady=5)
        
        common_commands = [
            ("设备列表", "devices"),
            ("重启", "reboot"),
            ("进入Recovery", "reboot recovery"),
            ("刷入boot", "flash boot boot.img"),
            ("解锁BL", "flashing unlock"),
            ("锁定BL", "flashing lock")
        ]
        
        for i, (text, cmd) in enumerate(common_commands):
            btn = ttk.Button(common_frame, text=text, 
                           command=lambda c=cmd: self._set_fastboot_command(c))
            btn.grid(row=i//3, column=i%3, padx=5, pady=5, sticky=tk.W)
        
        return tab
    
    def _create_unlock_tab(self):
        """创建BL解锁标签页"""
        tab = ttk.Frame(self.notebook)
        
        # 警告信息
        warning_frame = ttk.LabelFrame(tab, text="重要警告")
        warning_frame.pack(fill=tk.X, padx=10, pady=5)
        
        warning_label = ttk.Label(warning_frame, 
                                text="警告: 解锁Bootloader会清除设备上的所有数据!\n\n"
                                     "请在操作前备份重要数据。某些设备可能需要先申请解锁许可。",
                                foreground="red", justify=tk.CENTER)
        warning_label.pack(padx=10, pady=10)
        
        # 解锁按钮
        unlock_btn = ttk.Button(tab, text="解锁Bootloader", command=self._unlock_bootloader)
        unlock_btn.pack(padx=10, pady=5)
        
        # 锁定按钮
        lock_btn = ttk.Button(tab, text="锁定Bootloader", command=self._lock_bootloader)
        lock_btn.pack(padx=10, pady=5)
        
        # 状态显示
        status_frame = ttk.LabelFrame(tab, text="操作状态")
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.unlock_status = ttk.Label(status_frame, text="设备状态: 未知")
        self.unlock_status.pack(padx=10, pady=5)
        
        # 解锁说明
        instructions_frame = ttk.LabelFrame(tab, text="操作说明")
        instructions_frame.pack(fill=tk.X, padx=10, pady=5)
        
        instructions = ttk.Label(instructions_frame, 
                               text="解锁步骤:\n"
                                    "1. 确保设备已进入Fastboot模式\n"
                                    "2. 连接设备到电脑\n"
                                    "3. 点击解锁按钮\n"
                                    "4. 按照设备屏幕上的提示操作",
                               justify=tk.LEFT)
        instructions.pack(padx=10, pady=10)
        
        return tab
    
    def _create_xiaomi_tab(self):
        """创建小米线刷标签页"""
        tab = ttk.Frame(self.notebook)
        
        # 固件选择
        file_frame = ttk.LabelFrame(tab, text="小米线刷包")
        file_frame.pack(fill=tk.X, padx=10, pady=5)
        
        file_select_frame = ttk.Frame(file_frame)
        file_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.xiaomi_file_label = ttk.Label(file_select_frame, text="未选择小米线刷包")
        self.xiaomi_file_label.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(file_select_frame, text="选择线刷包", command=self._select_xiaomi_firmware).pack(side=tk.RIGHT, padx=5)
        
        # 刷机选项
        options_frame = ttk.LabelFrame(tab, text="刷机选项")
        options_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.clean_all_var = tk.BooleanVar(value=True)
        self.clean_all_check = ttk.Checkbutton(options_frame, text="清除所有数据", variable=self.clean_all_var)
        self.clean_all_check.pack(padx=10, pady=5, anchor=tk.W)
        
        self.lock_bootloader_var = tk.BooleanVar()
        self.lock_bootloader_check = ttk.Checkbutton(options_frame, text="锁定Bootloader", variable=self.lock_bootloader_var)
        self.lock_bootloader_check.pack(padx=10, pady=5, anchor=tk.W)
        
        # 进度条
        self.xiaomi_progress_var = tk.IntVar()
        self.xiaomi_progress_bar = ttk.Progressbar(tab, variable=self.xiaomi_progress_var, maximum=100)
        self.xiaomi_progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # 刷机按钮
        self.xiaomi_flash_btn = ttk.Button(tab, text="开始小米线刷", command=self._start_xiaomi_flashing)
        self.xiaomi_flash_btn.pack(padx=10, pady=10)
        
        return tab
    
    def _create_mtk_tab(self):
        """创建MTK工具标签页"""
        tab = ttk.Frame(self.notebook)
        
        # 说明
        info_frame = ttk.LabelFrame(tab, text="使用说明")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        info_label = ttk.Label(info_frame, text="MTK命令行模式允许直接执行MTKClient命令")
        info_label.pack(padx=10, pady=5)
        
        # 命令输入
        command_frame = ttk.LabelFrame(tab, text="MTK命令")
        command_frame.pack(fill=tk.X, padx=10, pady=5)
        
        command_input_frame = ttk.Frame(command_frame)
        command_input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.mtk_command_input = ttk.Entry(command_input_frame)
        self.mtk_command_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        self.mtk_command_input.insert(0, "detect")
        
        execute_btn = ttk.Button(command_input_frame, text="执行", command=self._execute_mtk_command)
        execute_btn.pack(side=tk.LEFT, padx=5)
        
        stop_btn = ttk.Button(command_input_frame, text="停止", command=self._stop_mtk_command)
        stop_btn.pack(side=tk.LEFT, padx=5)
        
        # 常用命令按钮
        common_frame = ttk.LabelFrame(tab, text="常用命令")
        common_frame.pack(fill=tk.X, padx=10, pady=5)
        
        common_commands = [
            ("检测设备", "detect"),
            ("分区表", "printgpt"),
            ("读取boot", "rf boot"),
            ("写入boot", "wf boot"),
            ("解锁设备", "da seccfg unlock"),
            ("读取分区", "rl"),
            ("写入分区", "wl"),
            ("备份分区", "dump")
        ]
        
        for i, (text, cmd) in enumerate(common_commands):
            btn = ttk.Button(common_frame, text=text, 
                           command=lambda c=cmd: self._set_mtk_command(c))
            btn.grid(row=i//4, column=i%4, padx=5, pady=5, sticky=tk.W)
        
        # 设备检测
        detect_frame = ttk.LabelFrame(tab, text="设备检测")
        detect_frame.pack(fill=tk.X, padx=10, pady=5)
        
        detect_btn_frame = ttk.Frame(detect_frame)
        detect_btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_detect_btn = ttk.Button(detect_btn_frame, text="持续检测设备", command=self._start_detect_mtk)
        self.start_detect_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_detect_btn = ttk.Button(detect_btn_frame, text="停止检测", command=self._stop_detect_mtk, state=tk.DISABLED)
        self.stop_detect_btn.pack(side=tk.LEFT, padx=5)
        
        self.mtk_status_var = tk.StringVar(value="设备状态: 未连接")
        self.mtk_status_label = ttk.Label(detect_frame, textvariable=self.mtk_status_var)
        self.mtk_status_label.pack(padx=10, pady=5)
        
        # 输出显示
        output_frame = ttk.LabelFrame(tab, text="命令输出")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.mtk_output = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD)
        self.mtk_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        return tab
    
    def _start_device_check(self):
        """启动设备检测线程"""
        self.running = True
        
        def check_loop():
            while self.running:
                try:
                    # 检查ADB设备
                    adb_devices = self.adb.devices()
                    if adb_devices:
                        self._update_mode("adb", adb_devices[0][0])
                        self._update_device_details(adb_devices[0][0])
                        time.sleep(3)
                        continue
                except Exception as e:
                    self._log_message(f"ADB设备检测错误: {str(e)}")
                
                # 检查Fastboot设备
                try:
                    fastboot_devices = self.adb.fastboot_devices()
                    if fastboot_devices:
                        self._update_mode("fastboot", fastboot_devices[0][0])
                        self._update_device_details(fastboot_devices[0][0])
                        time.sleep(3)
                        continue
                except Exception as e:
                    self._log_message(f"Fastboot设备检测错误: {str(e)}")
                
                # 检查MTK设备
                if self.mtk_detecting:  # 只有开始识别时才检测
                    try:
                        mtk_devices = self.adb.detect_mtk_devices()
                        if mtk_devices:
                            self._update_mode("mtk", mtk_devices[0][0])
                            self.mtk_status_var.set(f"设备状态: 已连接 (端口: {mtk_devices[0][0]})")
                            self.mtk_detecting = False  # 检测到设备后停止检测
                            self.stop_detect_btn.config(state=tk.DISABLED)
                            self.start_detect_btn.config(state=tk.NORMAL)
                            time.sleep(3)
                            continue
                    except Exception as e:
                        self._log_message(f"MTK设备检测错误: {str(e)}")
                        self.mtk_status_var.set(f"设备状态: 检测错误 - {str(e)}")
                
                # 没有检测到设备
                self._update_mode(None, None)
                self.device_details.config(text="设备详细信息将在此显示")
                self.mtk_status_var.set("设备状态: 未连接")
                time.sleep(3)
        
        self.check_thread = threading.Thread(target=check_loop, daemon=True)
        self.check_thread.start()
    
    def _update_device_details(self, device_id):
        """更新设备详细信息"""
        try:
            if self.current_mode == "adb":
                # 获取设备信息
                result = self.adb.execute_adb_command(f"-s {device_id} shell getprop")
                if result and result['success']:
                    props = result['output'].splitlines()
                    details = []
                    
                    # 提取重要属性
                    important_props = {
                        "ro.product.model": "型号",
                        "ro.product.brand": "品牌",
                        "ro.product.name": "产品名",
                        "ro.build.version.release": "Android版本",
                        "ro.build.id": "构建ID",
                        "ro.serialno": "序列号"
                    }
                    
                    for prop in props:
                        if "]: [" in prop:
                            key, value = prop.split("]: [")
                            key = key.strip("[")
                            value = value.strip("]")
                            if key in important_props:
                                details.append(f"{important_props[key]}: {value}")
                    
                    self.device_details.config(text="\n".join(details))
                else:
                    self.device_details.config(text="无法获取设备详细信息")
            
            elif self.current_mode == "fastboot":
                # 获取fastboot设备信息
                result = self.adb.execute_fastboot_command(f"-s {device_id} getvar all")
                if result and result['success']:
                    self.device_details.config(text=result['output'])
                else:
                    self.device_details.config(text="无法获取设备详细信息")
            
        except Exception as e:
            self._log_message(f"获取设备详细信息错误: {str(e)}")
    
    def _update_mode(self, mode, device_id):
        """更新设备模式"""
        if mode == self.current_mode and device_id == self.device_id:
            return
            
        self.current_mode = mode
        self.device_id = device_id
        
        if mode == "adb":
            self.device_status.config(text="ADB模式", foreground="green")
            self.device_info.config(text=f"设备ID: {device_id}")
            self._update_button_states()
        elif mode == "fastboot":
            self.device_status.config(text="Fastboot模式", foreground="blue")
            self.device_info.config(text=f"设备ID: {device_id}")
            self._update_button_states()
        elif mode == "mtk":
            self.device_status.config(text="MTK Bootrom模式", foreground="orange")
            self.device_info.config(text=f"设备端口: {device_id}")
            self._update_button_states()
        else:
            self.device_status.config(text="未连接设备", foreground="gray")
            self.device_info.config(text="")
            self._update_button_states()
    
    def _update_button_states(self):
        """更新按钮状态"""
        has_device = self.current_mode is not None
        
        self.bootloader_btn.config(state=tk.NORMAL if has_device and self.current_mode == "adb" else tk.DISABLED)
        self.recovery_btn.config(state=tk.NORMAL if has_device and self.current_mode == "adb" else tk.DISABLED)
        self.reboot_btn.config(state=tk.NORMAL if has_device else tk.DISABLED)
        self.detect_mtk_btn.config(state=tk.NORMAL)
        self.flash_btn.config(state=tk.NORMAL if has_device and bool(self.firmware_path) and self.current_mode == "fastboot" else tk.DISABLED)
        self.backup_btn.config(state=tk.NORMAL if has_device and bool(self.backup_path) and self.current_mode == "fastboot" else tk.DISABLED)
        self.xiaomi_flash_btn.config(state=tk.NORMAL if bool(self.xiaomi_flash_path) else tk.DISABLED)
    
    def _log_message(self, message):
        """记录日志消息"""
        self.status_var.set(message)
        logging.info(message)
    
    def _update_progress(self, value):
        """更新进度条"""
        self.progress_var.set(value)
        self.xiaomi_progress_var.set(value)
    
    def _enter_bootloader(self):
        """进入Bootloader模式"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self._log_message("尝试进入Bootloader模式...")
        
        try:
            success, error = self.adb.reboot("bootloader")
            if success:
                self._log_message("设备正在重启到Bootloader...")
            else:
                self._log_message(f"操作失败: {error}")
        except Exception as e:
            self._log_message(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _enter_recovery(self):
        """进入Recovery模式"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self._log_message("尝试进入Recovery模式...")
        
        try:
            success, error = self.adb.reboot("recovery")
            if success:
                self._log_message("设备正在重启到Recovery...")
            else:
                self._log_message(f"操作失败: {error}")
        except Exception as e:
            self._log_message(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _detect_mtk_devices(self):
        """检测MTK设备"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self._log_message("开始检测MTK设备...")
        self.mtk_output.delete(1.0, tk.END)
        
        try:
            # 启动MTKClient命令
            cmd = [sys.executable, self.adb.mtk_path, "detect"]
            self.mtk_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # 启动线程读取输出
            threading.Thread(target=self._read_mtk_output, daemon=True).start()
        except Exception as e:
            self._log_message(f"检测MTK设备失败: {str(e)}")
            self.operation_in_progress = False
    
    def _start_detect_mtk(self):
        """开始持续检测MTK设备"""
        self._log_message("开始持续检测MTK设备...")
        self.mtk_detecting = True
        self.start_detect_btn.config(state=tk.DISABLED)
        self.stop_detect_btn.config(state=tk.NORMAL)
        self.mtk_status_var.set("设备状态: 检测中...")
        
        # 启动新的检测线程
        threading.Thread(target=self._detect_mtk_continuous, daemon=True).start()
    
    def _detect_mtk_continuous(self):
        """持续检测MTK设备"""
        while self.mtk_detecting:
            try:
                # 执行检测命令
                cmd = [sys.executable, self.adb.mtk_path, "detect"]
                self.mtk_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # 读取输出
                while self.mtk_detecting:
                    output = self.mtk_process.stdout.readline()
                    if output == '' and self.mtk_process.poll() is not None:
                        break
                    if output:
                        self.mtk_output.insert(tk.END, output)
                        self.mtk_output.see(tk.END)
                
                # 检查是否检测到设备
                if self.mtk_detecting and self.mtk_process.poll() == 0:
                    # 尝试解析输出以获取设备信息
                    mtk_devices = self.adb.detect_mtk_devices()
                    if mtk_devices:
                        self._update_mode("mtk", mtk_devices[0][0])
                        self.mtk_detecting = False  # 检测到设备后停止检测
                        self.stop_detect_btn.config(state=tk.DISABLED)
                        self.start_detect_btn.config(state=tk.NORMAL)
                        self.mtk_status_var.set(f"设备状态: 已连接 (端口: {mtk_devices[0][0]})")
                        break
                
                time.sleep(1)
            except Exception as e:
                self.mtk_output.insert(tk.END, f"检测错误: {str(e)}\n")
                self.mtk_output.see(tk.END)
                self.mtk_status_var.set(f"设备状态: 检测错误 - {str(e)}")
                time.sleep(1)
    
    def _stop_detect_mtk(self):
        """停止检测MTK设备"""
        self._log_message("已停止检测MTK设备")
        self.mtk_detecting = False
        self.start_detect_btn.config(state=tk.NORMAL)
        self.stop_detect_btn.config(state=tk.DISABLED)
        self.mtk_status_var.set("设备状态: 检测已停止")
        
        # 如果检测进程仍在运行，终止它
        if self.mtk_process and self.mtk_process.poll() is None:
            try:
                self.mtk_process.terminate()
            except:
                pass
    
    def _reboot_device(self):
        """重启设备"""
        if self.operation_in_progress:
            return
            
        self.operation_in_progress = True
        self._log_message("正在重启设备...")
        
        try:
            if self.current_mode == "adb":
                success, error = self.adb.reboot()
                if not success:
                    self._log_message(f"重启失败: {error}")
            elif self.current_mode == "fastboot":
                success, error = self.adb.fastboot_reboot()
                if not success:
                    self._log_message(f"重启失败: {error}")
            elif self.current_mode == "mtk":
                self._log_message("MTK设备重启需要手动操作")
            else:
                self._log_message("当前模式不支持重启")
        except Exception as e:
            self._log_message(f"操作异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _select_firmware(self):
        """选择固件文件"""
        file_path = filedialog.askopenfilename(
            title="选择固件文件", 
            filetypes=[("固件文件", "*.zip *.tgz *.tar.gz *.img *.bin"), ("所有文件", "*.*")]
        )
            
        if file_path:
            self.firmware_path = file_path
            self.file_label.config(text=os.path.basename(file_path))
            self._update_button_states()
            self._log_message(f"已选择固件: {file_path}")
    
    def _select_xiaomi_firmware(self):
        """选择小米线刷包"""
        file_path = filedialog.askopenfilename(
            title="选择小米线刷包", 
            filetypes=[("小米线刷包", "*.tgz *.tar.gz"), ("所有文件", "*.*")]
        )
            
        if file_path:
            self.xiaomi_flash_path = file_path
            self.xiaomi_file_label.config(text=os.path.basename(file_path))
            self._update_button_states()
            self._log_message(f"已选择小米线刷包: {file_path}")
    
    def _select_backup_path(self):
        """选择备份路径"""
        backup_dir = filedialog.askdirectory(title="选择备份目录")
        
        if backup_dir:
            self.backup_path = backup_dir
            self.backup_path_label.config(text=os.path.basename(backup_dir))
            self._update_button_states()
            self._log_message(f"已选择备份路径: {backup_dir}")
    
    def _set_adb_command(self, command):
        """设置ADB命令"""
        self.adb_command_input.delete(0, tk.END)
        self.adb_command_input.insert(0, command)
    
    def _execute_adb_command(self):
        """执行ADB命令"""
        if self.operation_in_progress:
            return
            
        command = self.adb_command_input.get().strip()
        if not command:
            self._log_message("请输入ADB命令")
            return
            
        self.operation_in_progress = True
        self._log_message(f"执行ADB命令: {command}")
        
        try:
            result = self.adb.execute_adb_command(command)
            if result is None:
                self.adb_output.delete(1.0, tk.END)
                self.adb_output.insert(tk.END, f"执行失败: {self.adb.last_error}")
            else:
                output = ""
                if result['output']:
                    output += f"输出:\n{result['output']}\n\n"
                if result['error']:
                    output += f"错误:\n{result['error']}\n\n"
                output += f"结果: {'成功' if result['success'] else '失败'}"
                self.adb_output.delete(1.0, tk.END)
                self.adb_output.insert(tk.END, output)
                self._log_message(f"ADB命令执行{'成功' if result['success'] else '失败'}")
        except Exception as e:
            self.adb_output.delete(1.0, tk.END)
            self.adb_output.insert(tk.END, f"执行异常: {str(e)}")
            self._log_message(f"ADB命令执行异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _set_fastboot_command(self, command):
        """设置Fastboot命令"""
        self.fastboot_command_input.delete(0, tk.END)
        self.fastboot_command_input.insert(0, command)
    
    def _execute_fastboot_command(self):
        """执行Fastboot命令"""
        if self.operation_in_progress:
            return
            
        command = self.fastboot_command_input.get().strip()
        if not command:
            self._log_message("请输入Fastboot命令")
            return
            
        self.operation_in_progress = True
        self._log_message(f"执行Fastboot命令: {command}")
        
        try:
            result = self.adb.execute_fastboot_command(command)
            if result is None:
                self.fastboot_output.delete(1.0, tk.END)
                self.fastboot_output.insert(tk.END, f"执行失败: {self.adb.last_error}")
            else:
                output = ""
                if result['output']:
                    output += f"输出:\n{result['output']}\n\n"
                if result['error']:
                    output += f"错误:\n{result['error']}\n\n"
                output += f"结果: {'成功' if result['success'] else '失败'}"
                self.fastboot_output.delete(1.0, tk.END)
                self.fastboot_output.insert(tk.END, output)
                self._log_message(f"Fastboot命令执行{'成功' if result['success'] else '失败'}")
        except Exception as e:
            self.fastboot_output.delete(1.0, tk.END)
            self.fastboot_output.insert(tk.END, f"执行异常: {str(e)}")
            self._log_message(f"Fastboot命令执行异常: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def _set_mtk_command(self, command):
        """设置MTK命令"""
        self.mtk_command_input.delete(0, tk.END)
        self.mtk_command_input.insert(0, command)
    
    def _execute_mtk_command(self):
        """执行MTK命令"""
        if self.operation_in_progress:
            return
            
        command = self.mtk_command_input.get().strip()
        if not command:
            self._log_message("请输入MTK命令")
            return
            
        self.operation_in_progress = True
        self._log_message(f"执行MTK命令: {command}")
        self.mtk_output.delete(1.0, tk.END)
        self.mtk_output.insert(tk.END, f">>> {command}\n")
        
        try:
            # 分割命令为参数列表
            args = command.split()
            
            # 启动MTKClient命令
            if self.adb.mtk_path:
                cmd = [sys.executable, self.adb.mtk_path] + args
                
                # 启动子进程
                self.mtk_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # 启动线程读取输出
                threading.Thread(target=self._read_mtk_output, daemon=True).start()
            else:
                self._log_message("未找到MTKClient工具")
                self.operation_in_progress = False
        except Exception as e:
            self.mtk_output.insert(tk.END, f"执行异常: {str(e)}\n")
            self._log_message(f"MTK命令执行异常: {str(e)}")
            self.operation_in_progress = False
    
    def _read_mtk_output(self):
        """读取MTK命令输出"""
        try:
            while True:
                output = self.mtk_process.stdout.readline()
                if output == '' and self.mtk_process.poll() is not None:
                    break
                if output:
                    self.mtk_output.insert(tk.END, output)
                    self.mtk_output.see(tk.END)
            
            # 命令执行完成
            return_code = self.mtk_process.poll()
            if return_code == 0:
                self.mtk_output.insert(tk.END, "命令执行成功\n")
            else:
                self.mtk_output.insert(tk.END, f"命令执行失败，返回码: {return_code}\n")
        except Exception as e:
            self.mtk_output.insert(tk.END, f"读取输出错误: {str(e)}\n")
        finally:
            self.mtk_process = None
            self.operation_in_progress = False
            self.mtk_output.see(tk.END)
    
    def _stop_mtk_command(self):
        """停止当前MTK命令"""
        if self.mtk_process and self.mtk_process.poll() is None:
            try:
                self.mtk_process.terminate()
                self.mtk_output.insert(tk.END, "命令已终止\n")
            except Exception as e:
                self.mtk_output.insert(tk.END, f"终止命令失败: {str(e)}\n")
        else:
            self.mtk_output.insert(tk.END, "没有正在执行的命令\n")
    
    def _unlock_bootloader(self):
        """解锁Bootloader"""
        if self.operation_in_progress:
            return
            
        if not messagebox.askyesno("警告", "解锁Bootloader会清除设备上的所有数据!\n\n确定要继续吗?"):
            return
            
        self.operation_in_progress = True
        self._log_message("正在尝试解锁Bootloader...")
        
        try:
            success, error = self.adb.unlock_bootloader()
            if success:
                self._log_message("解锁Bootloader成功! 设备将自动重启")
                self.unlock_status.config(text="设备状态: 已解锁")
            else:
                self._log_message(f"解锁失败: {error}")
                self.unlock_status.config(text="设备状态: 解锁失败")
        except Exception as e:
            self._log_message(f"解锁异常: {str(e)}")
            self.unlock_status.config(text="设备状态: 解锁异常")
        finally:
            self.operation_in_progress = False
    
    def _lock_bootloader(self):
        """锁定Bootloader"""
        if self.operation_in_progress:
            return
            
        if not messagebox.askyesno("警告", "锁定Bootloader可能会影响系统更新和某些功能!\n\n确定要继续吗?"):
            return
            
        self.operation_in_progress = True
        self._log_message("正在尝试锁定Bootloader...")
        
        try:
            success, error = self.adb.lock_bootloader()
            if success:
                self._log_message("锁定Bootloader成功! 设备将自动重启")
                self.unlock_status.config(text="设备状态: 已锁定")
            else:
                self._log_message(f"锁定失败: {error}")
                self.unlock_status.config(text="设备状态: 锁定失败")
        except Exception as e:
            self._log_message(f"锁定异常: {str(e)}")
            self.unlock_status.config(text="设备状态: 锁定异常")
        finally:
            self.operation_in_progress = False
    
    def _start_flashing(self):
        """开始刷机"""
        if self.operation_in_progress or not self.firmware_path:
            return
            
        # 检查设备状态
        if self.current_mode != "fastboot":
            messagebox.showwarning("警告", "设备未处于Fastboot模式，无法刷机")
            return
            
        if not messagebox.askyesno("确认", "确定要刷机吗? 此操作有风险!"):
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_flash, daemon=True).start()
    
    def _start_xiaomi_flashing(self):
        """开始小米线刷"""
        if self.operation_in_progress or not self.xiaomi_flash_path:
            return
            
        if not messagebox.askyesno("确认", "确定要刷入小米线刷包吗? 此操作会清除所有数据!"):
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_xiaomi_flash, daemon=True).start()
    
    def _start_backup(self):
        """开始备份"""
        if self.operation_in_progress or not self.backup_path:
            return
            
        self.operation_in_progress = True
        threading.Thread(target=self._execute_backup, daemon=True).start()
    
    def _execute_flash(self):
        """执行刷机"""
        try:
            partition = self.partition_combo.get()
            self._log_message(f"开始刷写 {partition} 分区...")
            self._update_progress(0)
            
            # 如果是单个分区且固件是img或bin文件
            if partition != "全部" and (self.firmware_path.lower().endswith('.img') or 
                                       self.firmware_path.lower().endswith('.bin')):
                self._log_message(f"正在刷入 {partition} 分区...")
                
                if self.adb.flash_partition(partition, self.firmware_path):
                    self._log_message(f"{partition} 分区刷入成功!")
                    self._update_progress(100)
                else:
                    self._log_message(f"刷入失败: {self.adb.last_error}")
                    self._update_progress(0)
            else:
                # 处理固件包（zip/tar.gz等）
                temp_dir = tempfile.mkdtemp(prefix="firmware_")
                try:
                    # 解压固件包
                    if self.firmware_path.lower().endswith('.zip'):
                        with zipfile.ZipFile(self.firmware_path, 'r') as zip_ref:
                            zip_ref.extractall(temp_dir)
                    elif self.firmware_path.lower().endswith('.tar.gz') or self.firmware_path.lower().endswith('.tgz'):
                        with tarfile.open(self.firmware_path, 'r:gz') as tar_ref:
                            tar_ref.extractall(temp_dir)
                    else:
                        temp_dir = os.path.dirname(self.firmware_path)
                    
                    if partition == "全部":
                        # 查找所有镜像文件
                        img_files = []
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.lower().endswith('.img') or file.lower().endswith('.bin'):
                                    img_files.append(os.path.join(root, file))
                        
                        if not img_files:
                            self._log_message("在固件包中未找到任何镜像文件")
                            return
                        
                        total = len(img_files)
                        for i, img_file in enumerate(img_files):
                            # 提取分区名（不带扩展名）
                            partition_name = os.path.splitext(os.path.basename(img_file))[0]
                            self._log_message(f"正在刷写分区: {partition_name}")
                            
                            if self.adb.flash_partition(partition_name, img_file):
                                self._log_message(f"{partition_name} 刷写成功")
                            else:
                                self._log_message(f"{partition_name} 刷写失败: {self.adb.last_error}")
                            
                            # 更新进度
                            progress = int((i + 1) / total * 100)
                            self._update_progress(progress)
                        
                        self._log_message("所有分区刷写完成")
                    else:
                        # 查找特定分区镜像
                        img_file = None
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.lower().endswith(f"{partition}.img") or file.lower().endswith(f"{partition}.bin"):
                                    img_file = os.path.join(root, file)
                                    break
                            if img_file:
                                break
                        
                        if img_file:
                            self._log_message(f"找到分区镜像: {os.path.basename(img_file)}")
                            self._update_progress(50)
                            
                            if self.adb.flash_partition(partition, img_file):
                                self._log_message(f"{partition} 分区刷入成功!")
                                self._update_progress(100)
                            else:
                                self._log_message(f"{partition} 分区刷入失败: {self.adb.last_error}")
                                self._update_progress(0)
                        else:
                            self._log_message(f"在固件包中未找到 {partition} 分区镜像")
                finally:
                    if temp_dir != os.path.dirname(self.firmware_path):
                        shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            self._log_message(f"刷机失败: {str(e)}")
            self._update_progress(0)
        finally:
            self.operation_in_progress = False
    
    def _execute_xiaomi_flashing(self):
        """执行小米线刷"""
        try:
            self._log_message("开始小米线刷...")
            self._update_progress(0)
            
            # 解压线刷包
            temp_dir = tempfile.mkdtemp(prefix="xiaomi_flash_")
            try:
                if self.xiaomi_flash_path.endswith('.tgz') or self.xiaomi_flash_path.endswith('.tar.gz'):
                    with tarfile.open(self.xiaomi_flash_path, 'r:gz') as tar_ref:
                        tar_ref.extractall(temp_dir)
                else:
                    self._log_message("不支持的小米线刷包格式")
                    return
                
                # 查找flash_all脚本
                flash_script = None
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.startswith("flash_all") and (file.endswith(".bat") or file.endswith(".sh")):
                            flash_script = os.path.join(root, file)
                            break
                
                if flash_script:
                    self._log_message(f"正在执行刷机脚本: {os.path.basename(flash_script)}")
                    
                    # 根据操作系统选择执行方式
                    if platform.system().lower() == "windows" and flash_script.endswith(".bat"):
                        cmd = ["cmd", "/c", flash_script]
                    elif flash_script.endswith(".sh"):
                        cmd = ["bash", flash_script]
                    else:
                        cmd = [sys.executable, flash_script]
                    
                    # 执行刷机命令
                    process = subprocess.Popen(cmd, cwd=temp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                             text=True, encoding='utf-8', errors='ignore')
                    
                    # 读取输出并更新日志
                    while True:
                        output = process.stdout.readline()
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            self._log_message(output.strip())
                    
                    # 检查结果
                    if process.returncode == 0:
                        self._log_message("小米线刷完成!")
                        self._update_progress(100)
                    else:
                        self._log_message(f"小米线刷失败，返回码: {process.returncode}")
                        self._update_progress(0)
                else:
                    self._log_message("在刷机包中未找到flash_all脚本")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            self._log_message(f"小米线刷失败: {str(e)}")
            self._update_progress(0)
        finally:
            self.operation_in_progress = False
    
    def _execute_backup(self):
        """执行备份"""
        try:
            partition = self.backup_partition_combo.get()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self.backup_path, f"{partition}_backup_{timestamp}.img")
            
            self._log_message(f"开始备份 {partition} 分区...")
            
            if self.current_mode == "fastboot":
                if self.adb.backup_partition_fastboot(partition, backup_file):
                    self._log_message(f"备份成功: {backup_file}")
                else:
                    self._log_message(f"备份失败: {self.adb.last_error}")
            else:
                self._log_message("当前设备未处于Fastboot模式，无法备份")
        except Exception as e:
            self._log_message(f"备份失败: {str(e)}")
        finally:
            self.operation_in_progress = False
    
    def on_closing(self):
        """关闭窗口事件处理"""
        if self.operation_in_progress:
            messagebox.showwarning("警告", "请等待当前操作完成")
            return
            
        # 停止设备检测线程
        self.running = False
        # 等待线程结束，最多1秒
        if hasattr(self, 'check_thread') and self.check_thread.is_alive():
            self.check_thread.join(timeout=1.0)
        
        # 终止正在运行的MTK命令
        if self.mtk_process and self.mtk_process.poll() is None:
            try:
                self.mtk_process.terminate()
            except:
                pass
        
        self.adb.cleanup()
        self.destroy()

if __name__ == "__main__":
    app = FlashTool()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()