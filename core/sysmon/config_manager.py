import subprocess
import os
import sys
import win32service
import win32serviceutil
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, List

logger = logging.getLogger('IRtool')

_SUBPROCESS_KWARGS = {
    'creationflags': subprocess.CREATE_NO_WINDOW,
    'startupinfo': subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=subprocess.SW_HIDE),
}

EVENT_CONFIG = {
    'dns': {
        'name': 'DNS查询',
        'event_id': 22,
        'xml_tag': 'DnsQuery',
        'default': True,
    },
    'network': {
        'name': '网络连接',
        'event_id': 3,
        'xml_tag': 'NetworkConnect',
        'default': True,
    },
    'remote_thread': {
        'name': '远程线程创建',
        'event_id': 8,
        'xml_tag': 'CreateRemoteThread',
        'default': True,
    },
    'file_create_dll': {
        'name': 'DLL文件创建',
        'event_id': 11,
        'xml_tag': 'FileCreate',
        'default': False,
    },
}

DEFAULT_ENABLED_EVENTS = ['dns', 'network', 'remote_thread']


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
        logger.debug(f"SysmonConfigManager初始化: exe={self.sysmon_exe_path}, config={self.config_path}")

    def _find_sysmon_exe(self) -> Path:
        possible_names = ['sysmon64.exe', 'Sysmon64.exe', 'sysmon.exe', 'Sysmon.exe']
        base_dir = _get_app_dir()

        for name in possible_names:
            exe_path = base_dir / 'tools' / name
            if exe_path.exists():
                logger.debug(f"找到Sysmon可执行文件: {exe_path}")
                return exe_path

        for name in possible_names:
            result = self._find_in_path(name)
            if result:
                logger.debug(f"在PATH中找到Sysmon: {result}")
                return Path(result)

        default_path = base_dir / 'tools' / 'sysmon64.exe'
        logger.debug(f"使用默认Sysmon路径: {default_path}")
        return default_path

    def _find_config_path(self) -> Path:
        base_dir = _get_app_dir()
        config_path = base_dir / 'tools' / 'sysmon_config.xml'
        logger.debug(f"使用配置路径: {config_path}")
        return config_path

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
                installed = status[1] != 0
                if installed:
                    logger.debug(f"Sysmon服务已安装: {service_name}")
                return installed
            except Exception:
                continue
        return False

    def is_running(self) -> bool:
        for service_name in [self.SYSMON_SERVICE_NAME, self.SYSMON_SERVICE_NAME_ALT]:
            try:
                status = win32serviceutil.QueryServiceStatus(service_name)
                running = status[1] == win32service.SERVICE_RUNNING
                if running:
                    logger.debug(f"Sysmon服务运行中: {service_name}")
                return running
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
        logger.info("开始安装Sysmon...")

        if self.is_installed():
            logger.info("Sysmon已安装，跳过安装")
            return True, "Sysmon 已安装"

        if not self.sysmon_exe_path.exists():
            error_msg = f"找不到 Sysmon: {self.sysmon_exe_path}"
            logger.error(error_msg)
            return False, error_msg

        if not self.config_path.exists():
            error_msg = f"找不到配置文件: {self.config_path}"
            logger.error(error_msg)
            return False, error_msg

        logger.info(f"Sysmon路径: {self.sysmon_exe_path}")
        logger.info(f"配置文件: {self.config_path}")

        cmd = [str(self.sysmon_exe_path)]
        if accept_eula:
            cmd.append('-accepteula')
        cmd.extend(['-i', str(self.config_path)])

        cmd_str = ' '.join(cmd)
        logger.info(f"执行命令: {cmd_str}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                **_SUBPROCESS_KWARGS
            )

            logger.debug(f"命令返回码: {result.returncode}")
            if result.stdout:
                logger.debug(f"命令输出: {result.stdout}")
            if result.stderr:
                logger.debug(f"命令错误: {result.stderr}")

            if result.returncode == 0:
                self.mark_started_by_irtool()
                logger.info("Sysmon安装成功")
                return True, "Sysmon 安装成功"
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"Sysmon安装失败: {error_msg}")
                return False, f"安装失败: {error_msg}"

        except subprocess.TimeoutExpired:
            logger.error("Sysmon安装超时")
            return False, "安装超时"
        except Exception as e:
            logger.exception("Sysmon安装异常")
            return False, f"安装异常: {str(e)}"

    def uninstall(self) -> Tuple[bool, str]:
        logger.info("开始卸载Sysmon...")

        if not self.is_installed():
            logger.info("Sysmon未安装，无需卸载")
            return True, "Sysmon 未安装"

        cmd = [str(self.sysmon_exe_path), '-accepteula', '-u']
        logger.debug(f"执行命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                **_SUBPROCESS_KWARGS
            )

            logger.debug(f"命令返回码: {result.returncode}")
            if result.stdout:
                logger.debug(f"命令输出: {result.stdout}")
            if result.stderr:
                logger.debug(f"命令错误: {result.stderr}")

            if result.returncode == 0:
                self.clear_started_marker()
                logger.info("Sysmon卸载成功")
                return True, "Sysmon 卸载成功"
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"Sysmon卸载失败: {error_msg}")
                return False, f"卸载失败: {error_msg}"

        except subprocess.TimeoutExpired:
            logger.error("Sysmon卸载超时")
            return False, "卸载超时"
        except Exception as e:
            logger.exception("Sysmon卸载异常")
            return False, f"卸载异常: {str(e)}"

    def update_config(self, config_path: Optional[str] = None) -> Tuple[bool, str]:
        config = Path(config_path) if config_path else self.config_path
        logger.info(f"开始更新Sysmon配置: {config}")

        if not config.exists():
            error_msg = f"配置文件不存在: {config}"
            logger.error(error_msg)
            return False, error_msg

        if not self.is_installed():
            error_msg = "Sysmon 未安装，请先安装"
            logger.error(error_msg)
            return False, error_msg

        cmd = [str(self.sysmon_exe_path), '-c', str(config)]
        logger.debug(f"执行命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                **_SUBPROCESS_KWARGS
            )

            logger.debug(f"命令返回码: {result.returncode}")
            if result.stdout:
                logger.debug(f"命令输出: {result.stdout}")
            if result.stderr:
                logger.debug(f"命令错误: {result.stderr}")

            if result.returncode == 0:
                logger.info("Sysmon配置更新成功")
                return True, "配置更新成功"
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"Sysmon配置更新失败: {error_msg}")
                return False, f"配置更新失败: {error_msg}"

        except Exception as e:
            logger.exception("Sysmon配置更新异常")
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
            'config_managed_by_irtool': self.is_current_config_managed_by_irtool(),
        }

        info['installed'] = self.is_installed()
        if info['installed']:
            info['running'] = self.is_running()
            info['service_name'] = self.get_service_name()

        logger.debug(f"Sysmon状态信息: {info}")
        return info

    def mark_started_by_irtool(self):
        try:
            self._marker_file.write_text(str(os.getpid()), encoding='utf-8')
            logger.debug(f"标记Sysmon由IRtool启动: {self._marker_file}")
        except Exception as e:
            logger.warning(f"无法创建启动标记文件: {e}")

    def clear_started_marker(self):
        try:
            if self._marker_file.exists():
                self._marker_file.unlink()
                logger.debug(f"清除Sysmon启动标记: {self._marker_file}")
        except Exception as e:
            logger.warning(f"无法清除启动标记文件: {e}")

    def was_started_by_irtool(self) -> bool:
        started = self._marker_file.exists()
        if started:
            logger.debug("Sysmon是由IRtool启动的")
        return started

    def start_service(self) -> Tuple[bool, str]:
        """启动Sysmon服务（已安装但未运行时）"""
        service_name = self.get_service_name()
        if not service_name:
            error_msg = "未找到 Sysmon 服务"
            logger.error(error_msg)
            return False, error_msg

        logger.info(f"启动Sysmon服务: {service_name}")
        try:
            win32serviceutil.StartService(service_name)
            logger.info("Sysmon服务已启动")
            return True, "Sysmon 服务已启动"
        except win32service.error as e:
            # 错误码 5 = 拒绝访问
            if e.winerror == 5:
                logger.error(f"启动Sysmon服务被拒绝访问: {e}")
                return False, "启动服务失败: 拒绝访问（需要管理员权限）"
            elif e.winerror == 1056:
                logger.info("Sysmon服务已在运行中")
                return True, "服务已在运行"
            else:
                logger.exception("启动Sysmon服务失败")
                return False, f"启动服务失败: {e}"
        except Exception as e:
            logger.exception("启动Sysmon服务失败")
            return False, f"启动服务失败: {e}"

    def stop_service(self) -> Tuple[bool, str]:
        service_name = self.get_service_name()
        if not service_name:
            error_msg = "未找到 Sysmon 服务"
            logger.error(error_msg)
            return False, error_msg

        logger.info(f"停止Sysmon服务: {service_name}")
        try:
            win32serviceutil.StopService(service_name)
            logger.info("Sysmon服务已停止")
            return True, "Sysmon 服务已停止"
        except win32service.error as e:
            if e.winerror == 5:
                logger.error(f"停止Sysmon服务被拒绝访问: {e}")
                return False, "停止服务失败: 拒绝访问"
            elif e.winerror == 1052:
                logger.info("Sysmon服务已被标记为删除")
                return True, "服务已停止"
            elif e.winerror == 1062:
                logger.info("Sysmon服务未在运行")
                return True, "服务未在运行"
            else:
                logger.exception("停止Sysmon服务失败")
                return False, f"停止服务失败: {e}"
        except Exception as e:
            logger.exception("停止Sysmon服务失败")
            return False, f"停止服务失败: {e}"

    @staticmethod
    def generate_config(enabled_events: List[str]) -> str:
        logger.info(f"生成Sysmon配置，启用事件: {enabled_events}")

        all_tags = [
            ('ProcessCreate', '进程创建'),
            ('FileCreateTime', '文件创建时间修改'),
            ('NetworkConnect', '网络连接'),
            ('ProcessTerminate', '进程终止'),
            ('DriverLoad', '驱动加载'),
            ('ImageLoad', 'DLL加载'),
            ('CreateRemoteThread', '远程线程创建'),
            ('RawAccessRead', '原始磁盘访问'),
            ('ProcessAccess', '进程访问'),
            ('FileCreate', '文件创建'),
            ('RegistryEvent', '注册表事件'),
            ('FileCreateStreamHash', '文件流哈希'),
            ('PipeEvent', '管道事件'),
            ('WmiEvent', 'WMI事件'),
            ('DnsQuery', 'DNS查询'),
            ('FileDelete', '文件删除'),
            ('ClipboardChange', '剪贴板变化'),
            ('ProcessTampering', '进程篡改'),
            ('FileDeleteDetected', '文件删除检测'),
        ]

        enabled_tags = set()
        for key in enabled_events:
            if key in EVENT_CONFIG:
                enabled_tags.add(EVENT_CONFIG[key]['xml_tag'])

        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = ['<Sysmon schemaversion="4.90">']
        lines.append(f'  <!-- IRtool: Managed by IRtool - Generated at {timestamp} -->')
        lines.append(f'  <!-- IRtool: Enabled events: {", ".join(enabled_events)} -->')
        lines.append('  <EventFiltering>')

        for tag, desc in all_tags:
            if tag in enabled_tags:
                if tag == 'FileCreate' and 'file_create_dll' in enabled_events:
                    lines.append(f'    <!-- {desc} - 仅收集 DLL 文件 -->')
                    lines.append(f'    <{tag} onmatch="include">')
                    lines.append(f'      <TargetFilename condition="end with">.dll</TargetFilename>')
                    lines.append(f'    </{tag}>')
                else:
                    lines.append(f'    <!-- {desc} - 启用 -->')
                    lines.append(f'    <{tag} onmatch="exclude"/>')
            else:
                lines.append(f'    <!-- {desc} - 禁用 -->')
                lines.append(f'    <{tag} onmatch="include"/>')

        lines.append('  </EventFiltering>')
        lines.append('</Sysmon>')
        return '\n'.join(lines)

    @staticmethod
    def is_irtool_managed_config(config_content: str) -> bool:
        """检查配置是否由 IRtool 生成/管理

        通过查找 IRtool 特有的标记注释来判断
        """
        return '<!-- IRtool: Managed by IRtool' in config_content

    def is_current_config_managed_by_irtool(self) -> bool:
        """检查当前 Sysmon 使用的配置是否由 IRtool 管理

        通过读取当前配置文件内容判断
        """
        try:
            if not self.config_path.exists():
                return False
            config_content = self.config_path.read_text(encoding='utf-8')
            return self.is_irtool_managed_config(config_content)
        except Exception as e:
            logger.warning(f"无法读取配置文件判断是否由IRtool管理: {e}")
            return False

    def backup_current_config(self) -> Tuple[bool, str]:
        """备份当前配置文件到同目录

        返回: (是否成功, 备份路径或错误信息)
        """
        try:
            if not self.config_path.exists():
                return True, "无现有配置需要备份"

            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.config_path.parent / f"sysmon_config_backup_{timestamp}.xml"

            import shutil
            shutil.copy2(self.config_path, backup_path)
            logger.info(f"配置已备份到: {backup_path}")

            # 清理多余备份，保留最新 5 个
            try:
                backup_dir = self.config_path.parent
                backup_files = sorted(
                    backup_dir.glob('sysmon_config_backup_*.xml'),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True
                )
                for old_backup in backup_files[5:]:
                    old_backup.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"清理旧备份文件失败: {e}")

            return True, str(backup_path)
        except Exception as e:
            error_msg = f"备份配置失败: {e}"
            logger.error(error_msg)
            return False, error_msg

    def apply_config(self, enabled_events: List[str]) -> Tuple[bool, str]:
        logger.info(f"应用Sysmon配置，启用事件: {enabled_events}")

        # 如果不是IRtool管理的配置，先备份
        if self.config_path.exists() and not self.is_current_config_managed_by_irtool():
            logger.info("检测到非IRtool管理的配置，执行备份")
            backup_success, backup_msg = self.backup_current_config()
            if not backup_success:
                return False, f"无法备份现有配置: {backup_msg}"
            logger.info(f"原配置已备份: {backup_msg}")

        config_content = self.generate_config(enabled_events)

        config_dir = self.config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)

        try:
            self.config_path.write_text(config_content, encoding='utf-8')
            logger.info(f"配置文件已写入: {self.config_path}")
        except Exception as e:
            error_msg = f"写入配置文件失败: {e}"
            logger.error(error_msg)
            return False, error_msg

        if self.is_installed():
            success, msg = self.update_config()
            if success:
                return True, "配置已更新并应用"
            else:
                return False, f"配置已写入但应用失败: {msg}"
        else:
            return True, "配置已保存，安装Sysmon时将自动应用"

    @staticmethod
    def get_event_ids_for_config(enabled_events: List[str]) -> List[int]:
        event_ids = []
        for key in enabled_events:
            if key in EVENT_CONFIG:
                event_ids.append(EVENT_CONFIG[key]['event_id'])
        return sorted(event_ids)
