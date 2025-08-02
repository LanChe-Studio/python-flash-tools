import os
import re
import subprocess

import pkg_resources


def backup_partition_fastboot(self, partition, output_path):
    """使用Fastboot备份分区 - 修复分区大小解析问题"""
    if not self.fastboot_path:
        self.last_error = "Fastboot工具未找到"
        return False

    try:
        # 获取分区大小 - 使用更健壮的方法
        result = subprocess.run([self.fastboot_path, "getvar", "all"],
                                capture_output=True, text=True, encoding='utf-8', errors='ignore',
                                timeout=60)

        if result.returncode != 0:
            # 如果获取全部信息失败，尝试直接获取分区大小
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
        else:
            # 从全部信息中解析分区大小
            pattern = re.compile(rf"partition-size:{partition}:\s*(\d+)")
            match = pattern.search(result.stdout)
            if not match:
                self.last_error = f"在输出中找不到分区大小: {partition}"
                return False

            size_str = match.group(1)

        # 检查大小是否有效
        if not size_str.isdigit():
            # 尝试十六进制转换
            try:
                partition_size = int(size_str, 16)
            except:
                self.last_error = f"无效的分区大小: {size_str}"
                return False
        else:
            partition_size = int(size_str)

        # 备份分区
        self.last_error = f"开始备份 {partition} 分区 (大小: {partition_size} 字节)..."
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


def install_python_dependencies():
    """检测并安装必要的Python依赖"""
    required = ['PySide6', 'pyserial', 'requests', 'pyusb', 'libusb1', 'protobuf']
    missing = []

    for package in required:
        try:
            pkg_resources.require(package)
        except:
            missing.append(package)

    if missing:
        import subprocess
        for package in missing:
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            except:
                pass