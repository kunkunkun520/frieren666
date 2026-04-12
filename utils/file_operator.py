"""
文件操作工具 - 带详细日志
"""

import os
from pathlib import Path
from datetime import datetime


class FileOperator:
    """文件操作类，带详细日志"""

    def __init__(self):
        self.logs = []

    def _add_log(self, msg: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_msg = f"[{timestamp}] {msg}"
        self.logs.append(log_msg)
        print(log_msg)  # 打印到控制台

    def write_file(self, file_path: str, content: str) -> tuple:
        """
        写入文件（覆盖模式）
        返回: (success, message)
        """
        self._add_log(f"========== 开始写入文件 ==========")
        self._add_log(f"目标路径: {file_path}")
        self._add_log(f"文件内容长度: {len(content)} 字符")
        self._add_log(f"文件内容预览: {content[:200]}...")

        try:
            # 转换为Path对象
            path = Path(file_path)
            self._add_log(f"Path对象: {path}")

            # 检查路径是否存在
            self._add_log(f"路径是否存在: {path.exists()}")

            # 确保目录存在
            parent_dir = path.parent
            self._add_log(f"父目录: {parent_dir}")
            parent_dir.mkdir(parents=True, exist_ok=True)
            self._add_log(f"父目录已确保存在")

            # 写入文件
            self._add_log(f"开始写入文件...")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            self._add_log(f"文件写入完成")

            # 验证写入
            if path.exists():
                file_size = path.stat().st_size
                self._add_log(f"文件大小: {file_size} 字节")
                self._add_log(f"✅ 文件写入成功!")
                return True, f"文件已保存: {path}"
            else:
                self._add_log(f"❌ 文件写入后不存在!")
                return False, "文件写入后不存在"

        except PermissionError as e:
            self._add_log(f"❌ 权限错误: {str(e)}")
            return False, f"权限不足: {str(e)}"
        except OSError as e:
            self._add_log(f"❌ 系统错误: {str(e)}")
            return False, f"系统错误: {str(e)}"
        except Exception as e:
            self._add_log(f"❌ 未知错误: {str(e)}")
            return False, f"写入失败: {str(e)}"

    def read_file(self, file_path: str) -> tuple:
        """
        读取文件
        返回: (content, success, message)
        """
        self._add_log(f"========== 开始读取文件 ==========")
        self._add_log(f"目标路径: {file_path}")

        try:
            path = Path(file_path)
            if not path.exists():
                self._add_log(f"❌ 文件不存在")
                return "", False, f"文件不存在: {file_path}"

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            self._add_log(f"✅ 文件读取成功，长度: {len(content)} 字符")
            return content, True, "读取成功"

        except Exception as e:
            self._add_log(f"❌ 读取失败: {str(e)}")
            return "", False, str(e)

    def get_logs(self) -> list:
        """获取所有日志"""
        return self.logs

    def clear_logs(self):
        """清空日志"""
        self.logs = []


# 全局实例
file_operator = FileOperator()