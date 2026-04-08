# ui/autoruns_signature_worker.py
"""Autoruns 签名验证工作线程"""

# 标准库
import subprocess

# 第三方库
from PyQt6.QtCore import QThread, pyqtSignal

# 本地模块
from core.signature_parser import decode_sigcheck_bytes


class SignatureVerifyWorker(QThread):
    """签名验证线程，避免阻塞 UI"""

    succeeded = pyqtSignal(object)  # payload dict
    failed = pyqtSignal(object)  # payload dict

    def __init__(self, entry_id: str, image_path: str,
                 sigcheck_path: str, encoding: str):
        super().__init__()
        self.entry_id = entry_id
        self.image_path = image_path
        self.sigcheck_path = sigcheck_path
        self.encoding = encoding

    def run(self) -> None:
        """执行签名验证"""
        cmd = [self.sigcheck_path, '-accepteula', '-nobanner', self.image_path]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            stdout = decode_sigcheck_bytes(result.stdout, preferred_encoding=self.encoding)
            stderr = decode_sigcheck_bytes(result.stderr, preferred_encoding=self.encoding)
            if result.returncode == 0:
                self.succeeded.emit(
                    {
                        "entry_id": self.entry_id,
                        "image_path": self.image_path,
                        "output": stdout.strip(),
                    }
                )
                return
            self.failed.emit(
                {
                    "entry_id": self.entry_id,
                    "image_path": self.image_path,
                    "error_msg": stderr.strip() or "Unknown error",
                    "severity": "warning",
                }
            )
        except subprocess.TimeoutExpired:
            self.failed.emit(
                {
                    "entry_id": self.entry_id,
                    "image_path": self.image_path,
                    "error_msg": "签名验证超时",
                    "severity": "critical",
                }
            )
        except Exception as exc:
            self.failed.emit(
                {
                    "entry_id": self.entry_id,
                    "image_path": self.image_path,
                    "error_msg": str(exc),
                    "severity": "critical",
                }
            )


__all__ = ['SignatureVerifyWorker']