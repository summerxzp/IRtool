import subprocess
import os
import sys
import win32service
import win32serviceutil
from pathlib import Path
from typing import Tuple, Optional


def _get_app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
        internal_dir = base / '_internal'
        if internal_dir.exists():
            return internal_dir
        return base
    else:
        return Path(__file__).parent.parent.parent


class SysmonConfigManager:
    SYSMON_SERVICE_NAME = "Sysmon64"
    SYSMON_SERVICE_NAME_ALT = "Sysmon"

    def __init__(self, sysmon_exe_path: Optional[str] = None, config_path: Optional[str] = None):
        if sysmon_exe_path:
            self.sysmon_exe_path = Path(sysmon_exe_path)
        else:
            self.sysmon_exe_path = self._find_sysmon_exe()

        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = self._find_config_path()

        self._marker_file = _get_app_dir() / '.sysmon_started_by_irtool'

    def _find_sysmon_exe(self) -> Path:
        possible_names = ['sysmon64.exe', 'Sysmon64.exe', 'sysmon.exe', 'Sysmon.exe']
        base_dir = _get_app_dir()

        for name in possible_names:
            exe_path = base_dir / 'tools' / name
            if exe_path.exists():
                return exe_path

        for name in possible_names:
            result = self._find_in_path(name)
            if result:
                return Path(result)

        return base_dir / 'tools' / 'sysmon64.exe'

    def _find_config_path(self) -> Path:
        base_dir = _get_app_dir()

        config_path = base_dir / 'tools' / 'sysmon_config.xml'
        if config_path.exists():
            return config_path

        return base_dir / 'tools' / 'sysmon_config.xml'

    def _find_in_path(self, filename: str) -> Optional[str]:
        for path in os.environ.get('PATH', '').split(os.pathsep):
            full_path = os.path.join(path, filename)
            if os.path.isfile(full_path):
                return full_path
        return None

    def is_installed(self) -> bool:
        for service_name in [self.SYSMON_SERVICE_NAME, self.SYSMON_SERVICE_NAME_ALT]:
            try:
                status = win32serviceutil.QueryServiceStatus(service_name)
                return status[1] != 0
            except Exception:
                continue
        return False

    def is_running(self) -> bool:
        for service_name in [self.SYSMON_SERVICE_NAME, self.SYSMON_SERVICE_NAME_ALT]:
            try:
                status = win32serviceutil.QueryServiceStatus(service_name)
                return status[1] == win32service.SERVICE_RUNNING
            except Exception:
                continue
        return False

    def get_service_name(self) -> Optional[str]:
        for service_name in [self.SYSMON_SERVICE_NAME, self.SYSMON_SERVICE_NAME_ALT]:
            try:
                win32serviceutil.QueryServiceStatus(service_name)
                return service_name
            except Exception:
                continue
        return None

    def install(self, accept_eula: bool = True) -> Tuple[bool, str]:
        if self.is_installed():
            return True, "Sysmon 已安装"

        if not self.sysmon_exe_path.exists():
            return False, f"找不到 Sysmon: {self.sysmon_exe_path}"

        cmd = [str(self.sysmon_exe_path)]
        if accept_eula:
            cmd.append('-accepteula')
        cmd.extend(['-i', str(self.config_path)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                shell=True
            )

            if result.returncode == 0:
                return True, "Sysmon 安装成功"
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return False, f"安装失败: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "安装超时"
        except Exception as e:
            return False, f"安装异常: {str(e)}"

    def uninstall(self) -> Tuple[bool, str]:
        if not self.is_installed():
            return True, "Sysmon 未安装"

        cmd = [str(self.sysmon_exe_path), '-u']

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                shell=True
            )

            if result.returncode == 0:
                return True, "Sysmon 卸载成功"
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return False, f"卸载失败: {error_msg}"

        except subprocess.TimeoutExpired:
            return False, "卸载超时"
        except Exception as e:
            return False, f"卸载异常: {str(e)}"

    def update_config(self, config_path: Optional[str] = None) -> Tuple[bool, str]:
        config = Path(config_path) if config_path else self.config_path

        if not config.exists():
            return False, f"配置文件不存在: {config}"

        if not self.is_installed():
            return False, "Sysmon 未安装，请先安装"

        cmd = [str(self.sysmon_exe_path), '-c', str(config)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                shell=True
            )

            if result.returncode == 0:
                return True, "配置更新成功"
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return False, f"配置更新失败: {error_msg}"

        except Exception as e:
            return False, f"配置更新异常: {str(e)}"

    def get_status_info(self) -> dict:
        info = {
            'installed': False,
            'running': False,
            'service_name': None,
            'sysmon_exe_exists': self.sysmon_exe_path.exists(),
            'config_exists': self.config_path.exists(),
            'sysmon_exe_path': str(self.sysmon_exe_path),
            'config_path': str(self.config_path),
            'started_by_irtool': self.was_started_by_irtool(),
        }

        info['installed'] = self.is_installed()
        if info['installed']:
            info['running'] = self.is_running()
            info['service_name'] = self.get_service_name()

        return info

    def mark_started_by_irtool(self):
        try:
            self._marker_file.write_text(str(os.getpid()), encoding='utf-8')
        except Exception:
            pass

    def clear_started_marker(self):
        try:
            if self._marker_file.exists():
                self._marker_file.unlink()
        except Exception:
            pass

    def was_started_by_irtool(self) -> bool:
        return self._marker_file.exists()

    def stop_service(self) -> Tuple[bool, str]:
        service_name = self.get_service_name()
        if not service_name:
            return False, "未找到 Sysmon 服务"
        try:
            win32serviceutil.StopService(service_name)
            return True, "Sysmon 服务已停止"
        except Exception as e:
            return False, f"停止服务失败: {e}"
