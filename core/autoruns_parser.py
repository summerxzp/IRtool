# core/autoruns_parser.py
import subprocess
import csv
import hashlib
import os
import time
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Tuple
from pathlib import Path
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows API for hiding console window
import ctypes
from subprocess import CREATE_NO_WINDOW, SW_HIDE

@dataclass
class AutorunEntry:
    """自启动项数据模型"""
    location: str           # 位置类型 (Logon, Services, Tasks, etc.)
    entry: str             # 条目名称
    enabled: str           # 是否启用
    category: str          # 类别
    description: str       # 描述
    publisher: str         # 发布者
    company: str           # 公司
    image_path: str        # 文件路径
    launch_string: str     # 启动命令
    timestamp: str = ""    # 时间戳 (可选)
    md5: str = ""          # MD5 (可选)
    sha256: str = ""       # SHA256 (可选)
    signer: str = ""       # 签名者
    signer_status: str = "" # 签名状态 (Verified, Not Verified, etc.)
    signature_detail: str = "" # 签名详细信息
    file_size: str = ""     # 文件大小
    file_version: str = ""   # 文件版本
    service_name: str = ""   # 服务名称（仅用于 Services 类型）
    file_exists: bool = True  # 文件是否存在（预先检查）
    
    def get_detail_data(self):
        """获取结构化的 detail 数据对象"""
        return {
            "image_path": self.image_path,
            "command_line": self.launch_string,
            "category": self.category,
            "timestamp": self.timestamp,
            "signature": self._normalize_signature_status(),
            "publisher": self.publisher,
            "company": self.company,
            "size": self.file_size,
            "version": self.file_version,
            "hash": self.sha256
        }
    
    def _normalize_signature_status(self):
        """归一化签名状态"""
        if '(Verified)' in self.signer_status:
            return "Verified"
        elif '(Error)' in self.signer_status:
            return "Error"
        else:
            return "Unsigned"
    
    def to_dict(self):
        data = asdict(self)
        data['command_line'] = self.launch_string
        return data

class AutorunsParser:
    """Autoruns解析器"""

    def __init__(self, autoruns_path: str = None):
        # 默认从程序目录下的tools文件夹查找
        if autoruns_path is None:
            base_dir = self._get_app_dir()
            # 尝试多个路径: 1) 根目录/tools 2) _internal/tools (PyInstaller onedir)
            possible_paths = [
                base_dir / "tools" / "autorunsc64.exe",
                base_dir / "_internal" / "tools" / "autorunsc64.exe",
            ]
            self.autoruns_path = None
            for path in possible_paths:
                if path.exists():
                    self.autoruns_path = str(path)
                    break
            if self.autoruns_path is None:
                # 使用第一个路径作为默认值(会报错提示)
                self.autoruns_path = str(possible_paths[0])
        else:
            self.autoruns_path = autoruns_path

        self._verify_autoruns()

    def _get_app_dir(self) -> Path:
        """获取应用根目录（支持源码运行和PyInstaller打包）"""
        import sys
        if getattr(sys, 'frozen', False):
            # PyInstaller打包后，使用可执行文件所在目录
            return Path(sys.executable).parent
        else:
            # 源码运行，使用脚本所在目录
            return Path(__file__).parent.parent
    
    def _verify_autoruns(self):
        """验证autoruns是否存在"""
        if not os.path.exists(self.autoruns_path):
            raise FileNotFoundError(
                f"autorunsc64.exe not found at {self.autoruns_path}"
            )
    
    def scan(self, 
             include_hash: bool = False,
             verify_signature: bool = False,
             category_filter: Optional[List[str]] = None) -> List[AutorunEntry]:
        """
        执行autoruns扫描（使用固定参数与Sysinternals Autoruns GUI一致）
        
        参数:
            include_hash: 是否计算文件hash（当前固定为False，由参数控制）
            verify_signature: 是否验证签名（当前固定为False，由参数控制）
            category_filter: 类别过滤
        """
        # 固定参数，与Sysinternals Autoruns GUI一致
        cmd = [
            self.autoruns_path,
            '-accepteula',
            '-a', '*',
            '-c',
            '-s',
            '-nobanner'
        ]
        
        # 根据参数决定是否添加 -h 和 -v (但按要求默认为False)
        if include_hash:
            cmd.append('-h')  # 包含hash
        
        if verify_signature:
            cmd.append('-v')  # 验证签名

        try:
            # Hide console window on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            stdout_bytes, stderr_bytes = process.communicate(timeout=180)  # 3分钟超时

        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise RuntimeError("Autoruns 扫描超时")

        if process.returncode != 0:
            stderr = stderr_bytes.decode(errors='ignore')
            raise RuntimeError(f"Autoruns 执行失败: {stderr}")

        # === 关键修复：UTF-16LE 解码 ===
        try:
            csv_text = stdout_bytes.decode('utf-16le', errors='ignore')
        except Exception as e:
            raise RuntimeError(f"Autoruns 输出解码失败: {e}")

        entries = self._parse_csv(csv_text)

        # 类别过滤 - 使用 Category 字段而不是 Entry Location
        if category_filter:
            entries = [e for e in entries if e.category in category_filter]

        return entries


    
        


    def _batch_check_files(self, image_paths: List[str]) -> Dict[str, Tuple[bool, str]]:
        """
        批量并行检查文件存在性和大小
        返回: {image_path: (exists, file_size)}
        """
        results = {}
        
        def check_file(path: str) -> Tuple[str, bool, str]:
            """检查单个文件，返回 (path, exists, size)"""
            if not path or path.lower() == 'file not found':
                return path, False, ''
            try:
                exists = os.path.exists(path)
                size = ''
                if exists:
                    size = str(os.path.getsize(path))
                return path, exists, size
            except Exception:
                return path, False, ''
        
        # 使用线程池并行处理，最大20个线程
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_path = {
                executor.submit(check_file, path): path 
                for path in image_paths if path
            }
            
            for future in as_completed(future_to_path):
                path, exists, size = future.result()
                results[path] = (exists, size)
        
        return results

    def _parse_csv(self, csv_content: str) -> List[AutorunEntry]:
        entries = []
        raw_rows = []

        # 去除 UTF-8 BOM（在 splitlines 之前）
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]

        lines = csv_content.splitlines()
        if len(lines) < 2:
            return entries

        reader = csv.DictReader(lines)

        # 如果关键字段不存在，直接返回（避免假空）
        if not reader.fieldnames or 'Entry Location' not in reader.fieldnames:
            return entries

        # 第一遍：收集所有原始数据和需要检查的文件路径
        image_paths_to_check = set()
        for row in reader:
            try:
                image_path = row.get('Image Path', '').strip() if row.get('Image Path') else ''
                category = row.get('Category', '').strip() if row.get('Category') else ''
                entry_name = row.get('Entry', '').strip() if row.get('Entry') else ''
                
                if image_path and image_path.lower() != 'file not found':
                    image_paths_to_check.add(image_path)
                
                raw_rows.append({
                    'row': row,
                    'image_path': image_path,
                    'category': category,
                    'entry_name': entry_name
                })
            except Exception:
                continue

        # 第二遍：批量并行检查文件存在性和大小
        file_info_cache = self._batch_check_files(list(image_paths_to_check))

        # 第三遍：构建 AutorunEntry 对象
        for data in raw_rows:
            try:
                row = data['row']
                image_path = data['image_path']
                category = data['category']
                entry_name = data['entry_name']
                
                file_version = row.get('Version', '').strip() if row.get('Version') else ''
                
                # 从缓存获取文件信息
                file_exists, file_size = file_info_cache.get(image_path, (False, ''))
                
                # 解析服务名称（仅用于 Services 类型）
                service_name = ''
                if category == 'Services':
                    service_name = entry_name
                
                entries.append(AutorunEntry(
                    location=row.get('Entry Location', '').strip() if row.get('Entry Location') else '',
                    entry=entry_name,
                    enabled=row.get('Enabled', '').strip() if row.get('Enabled') else '',
                    category=category,
                    description=row.get('Description', '').strip() if row.get('Description') else '',
                    publisher=row.get('Company', '').strip() if row.get('Company') else '',
                    company=row.get('Company', '').strip() if row.get('Company') else '',
                    image_path=image_path,
                    launch_string=row.get('Launch String', '').strip() if row.get('Launch String') else '',
                    timestamp=row.get('Time', '').strip() if row.get('Time') else '',
                    md5=row.get('MD5', '') if row.get('MD5') else '',
                    sha256=row.get('SHA-256', '') if row.get('SHA-256') else '',
                    signer=row.get('Signer', '') if row.get('Signer') else '',
                    signer_status=row.get('Signer', '').strip() if row.get('Signer') else '',
                    signature_detail='',
                    file_size=file_size,
                    file_version=file_version,
                    service_name=service_name,
                    file_exists=file_exists
                ))
            except Exception:
                continue

        return entries

    
    def delete_entry(self, entry: AutorunEntry) -> tuple:
        r"""
        删除自启动项
        
        注意: 这是危险操作，需要管理员权限
        
        分发策略: 基于 location + category 进行路由，优先级从高到低:
        1. Services (service_name 非空)
        2. Winlogon/Credential Providers (location 含 Credential Providers)
        3. Winlogon/Notify (location 含 Winlogon\Notify)
        4. LSA Providers/Authentication Packages (location 含 Authentication Packages)
        5. LSA Providers/Security Packages (location 含 Security Packages)
        6. Tasks/Scheduled Tasks (category 为 Tasks 或 Scheduled Tasks)
        7. Boot Execute (location 含 BootExecute)
        8. KnownDLLs (location 含 KnownDLLs)
        9. AppInit_DLLs (location 含 AppInit_DLLs)
        10. Registry Run keys (location 含 Run/RunOnce)
        11. Image File Execution Options (location 含 IFEO)
        12. Fallback: 其他注册表项
        
        注意: Winlogon Shell/Userinit 已禁用删除功能，因对系统启动至关重要
        """
        try:
            print(f"[Parser] delete_entry 开始")
            print(f"[Parser] entry.location: {entry.location}")
            print(f"[Parser] entry.entry: {entry.entry}")
            print(f"[Parser] entry.launch_string: {entry.launch_string}")
            print(f"[Parser] entry.service_name: {entry.service_name}")
            print(f"[Parser] entry.category: {entry.category}")
            
            # 1. Services (最高优先级)
            if entry.service_name:
                print(f"[Parser] 识别为服务类型（通过 service_name）")
                return self._delete_service(entry)
            
            # 2. Winlogon/Credential Providers (删除注册表子键)
            if entry.location and 'Credential Providers' in entry.location:
                print(f"[Parser] 识别为 Winlogon/Credential Providers 类型")
                return self._delete_registry_key(entry)
            
            # 3. Winlogon/Notify (删除注册表子键)
            if entry.location and 'Winlogon\\Notify' in entry.location:
                print(f"[Parser] 识别为 Winlogon/Notify 类型")
                return self._delete_registry_key(entry)
            
            # 4. LSA Providers/Authentication Packages (编辑 REG_MULTI_SZ)
            if entry.location and 'Authentication Packages' in entry.location:
                print(f"[Parser] 识别为 LSA/Authentication Packages 类型")
                return self._delete_lsa_auth_package(entry, 'Authentication Packages')
            
            # 5. LSA Providers/Security Packages (编辑 REG_MULTI_SZ)
            if entry.location and 'Security Packages' in entry.location:
                print(f"[Parser] 识别为 LSA/Security Packages 类型")
                return self._delete_lsa_auth_package(entry, 'Security Packages')
            
            # 6. Scheduled Task
            if entry.category in ("Scheduled Tasks", "Tasks") or 'Task' in entry.location:
                print(f"[Parser] 识别为计划任务类型")
                return self._delete_scheduled_task(entry)
            
            # 7. Boot Execute (编辑 REG_MULTI_SZ)
            if entry.location and 'BootExecute' in entry.location:
                print(f"[Parser] 识别为 Boot Execute 类型")
                return self._delete_boot_execute_entry(entry)
            
            # 8. KnownDLLs (删除注册表值)
            if entry.location and 'KnownDLLs' in entry.location:
                print(f"[Parser] 识别为 KnownDLLs 类型")
                return self._delete_registry_entry(entry)
            
            # 9. AppInit_DLLs (编辑 REG_SZ 值，移除指定 DLL)
            if entry.location and 'AppInit_DLLs' in entry.location:
                print(f"[Parser] 识别为 AppInit_DLLs 类型")
                return self._delete_appinit_dlls_entry(entry)
            
            # 10. Winlogon Shell/Userinit - 已禁用删除功能
             # 这两个值对系统启动至关重要，误删会导致无法登录
             # 如需修改，请使用注册表编辑器手动操作
            
            # 11. Registry Run keys (删除注册表值)
            if entry.location and ('Run' in entry.location or 'RunOnce' in entry.location):
                print(f"[Parser] 识别为注册表 Run/RunOnce 类型")
                return self._delete_registry_entry(entry)
            
            # 12. Image File Execution Options (IFEO)
            if entry.location and 'Image File Execution Options' in entry.location:
                print(f"[Parser] 识别为 IFEO 类型")
                return self._delete_ifeo_entry(entry)
            
            # 13. Fallback: 尝试作为注册表值删除
            if entry.location and ('HKLM' in entry.location or 'HKCU' in entry.location):
                print(f"[Parser] 尝试作为注册表值删除")
                return self._delete_registry_entry(entry)
            
            # 14. 完全不支持的类型
            print(f"[Parser] 不支持的类型")
            return False, "不支持删除此类型的启动项"
        except Exception as e:
            import traceback
            print(f"[Parser] delete_entry 错误: {e}")
            print(f"[Parser] 错误堆栈:\n{traceback.format_exc()}")
            return False, str(e)
    
    def _parse_location(self, location: str):
        """
        解析 location 字符串为 (root_hkey, key_path)
        
        Args:
            location: 注册表路径，如 HKLM\SOFTWARE\Microsoft\...
        
        Returns:
            (winreg.HKEY_*, key_path_str) 或 (None, None) 如果无法解析
        """
        import winreg
        
        if not location:
            return None, None
        
        _ROOT_MAP = {
            'HKLM': winreg.HKEY_LOCAL_MACHINE,
            'HKCU': winreg.HKEY_CURRENT_USER,
            'HKCR': winreg.HKEY_CLASSES_ROOT,
            'HKU': winreg.HKEY_USERS,
        }
        
        for prefix, hkey in _ROOT_MAP.items():
            if location.startswith(prefix + '\\') or location == prefix:
                key_path = location[len(prefix):].lstrip('\\')
                return hkey, key_path
        
        return None, None
    
    def _delete_registry_entry(self, entry: AutorunEntry) -> tuple:
        """
        删除注册表值 (DeleteValue)
        
        适用于: Run/RunOnce、Shell、Userinit 等标准注册表启动项
        其中 entry.entry 是注册表值名称，entry.location 是所在键路径
        """
        import winreg
        
        root, key_path = self._parse_location(entry.location)
        if root is None:
            return False, f"无法解析注册表路径: {entry.location}"
        
        try:
            with winreg.OpenKey(root, key_path, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
                winreg.DeleteValue(key, entry.entry)
            return True, f"已删除注册表项: {entry.entry}"
        except PermissionError:
            return False, "权限不足，请以管理员身份运行"
        except FileNotFoundError:
            return False, "注册表项不存在"
        except OSError as e:
            return False, f"删除失败: {e}"
    
    def _delete_registry_key(self, entry: AutorunEntry) -> tuple:
        """
        删除注册表子键 (DeleteKey)
        
        适用于: Credential Providers、Winlogon Notify、Shell Execute Hooks 等
        其中 entry.entry 是子键名称（或 CLSID），entry.location 是父键路径
        
        特殊处理:
        - Credential Providers: entry 可能是显示名，需要从 launch_string 提取 CLSID
        - 其他类型: 直接使用 entry 作为子键名
        """
        import winreg
        import re
        
        root, parent_path = self._parse_location(entry.location)
        if root is None:
            return False, f"无法解析注册表路径: {entry.location}"
        
        subkey_name = entry.entry
        
        if 'Credential Providers' in (entry.location or ''):
            clsid_match = re.search(r'\{[0-9a-fA-F-]{36}\}', entry.launch_string or '')
            if clsid_match:
                subkey_name = clsid_match.group(0)
                print(f"[Parser] 从 launch_string 提取 CLSID 子键名: {subkey_name}")
        
        print(f"[Parser] _delete_registry_key: root={root}, parent={parent_path}, subkey={subkey_name}")
        
        try:
            with winreg.OpenKey(root, parent_path, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as parent_key:
                winreg.DeleteKey(parent_key, subkey_name)
            return True, f"已删除注册表子键: {subkey_name}"
        except PermissionError:
            return False, "权限不足，请以管理员身份运行"
        except FileNotFoundError:
            return False, "注册表子键不存在"
        except OSError as e:
            return False, f"删除子键失败: {e}"
    
    def _delete_lsa_auth_package(self, entry: AutorunEntry, value_name: str) -> tuple:
        """
        从 LSA 的 REG_MULTI_SZ 值中移除指定条目
        
        适用于: LSA Authentication Packages / Security Packages / Notification Packages
        这些值类型为 REG_MULTI_SZ（多字符串数组），不能直接 DeleteValue，
        需要读取→过滤→写回
        """
        import winreg
        
        LSA_KEY_PATH = r'SYSTEM\CurrentControlSet\Control\Lsa'
        
        target_string = entry.entry or entry.launch_string or ''
        if not target_string:
            return False, "无法确定要移除的条目内容"
        
        print(f"[Parser] _delete_lsa_auth_package: value_name={value_name}, target={target_string}")
        
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, LSA_KEY_PATH, 0,
                               winreg.KEY_SET_VALUE | winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as lsa_key:
                current_value, value_type = winreg.QueryValueEx(lsa_key, value_name)
                
                if value_type != winreg.REG_MULTI_SZ:
                    return False, f"期望 REG_MULTI_SZ 类型，实际为 {value_type}"
                
                if target_string not in current_value:
                    return False, f"目标条目不在 {value_name} 中"
                
                updated_value = [item for item in current_value if item != target_string]
                
                winreg.SetValueEx(lsa_key, value_name, 0, winreg.REG_MULTI_SZ, updated_value)
                
                return True, f"已从 {value_name} 中移除: {target_string}"
                
        except PermissionError:
            return False, "权限不足，请以管理员身份运行"
        except FileNotFoundError:
            return False, "LSA 注册表键不存在"
        except OSError as e:
            return False, f"编辑 LSA 配置失败: {e}"
    
    def _delete_ifeo_entry(self, entry: AutorunEntry) -> tuple:
        """
        删除 Image File Execution Options (IFEO) 条目
        
        IFEO 有两种形式:
        1. Debugger 值劫持: location=...\\IFEO\\notepad.exe, entry=Debugger → DeleteValue
        2. 整个子键被恶意创建: location=...\\IFEO\\malicious.exe → DeleteKey(整个子键)
        
        策略: 优先尝试删除指定值，若失败则删除整个子键
        """
        import winreg
        
        root, key_path = self._parse_location(entry.location)
        if root is None:
            return False, f"无法解析注册表路径: {entry.location}"
        
        print(f"[Parser] _delete_ifeo_entry: key_path={key_path}, entry={entry.entry}")
        
        try:
            with winreg.OpenKey(root, key_path, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
                if entry.entry and entry.entry not in ('(Default)', ''):
                    try:
                        winreg.DeleteValue(key, entry.entry)
                        return True, f"已删除 IFEO 值: {entry.entry}"
                    except FileNotFoundError:
                        pass
            
            parent_path = key_path.rsplit('\\', 1)[0]
            subkey_name = key_path.rsplit('\\', 1)[-1]
            
            with winreg.OpenKey(root, parent_path, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as parent_key:
                winreg.DeleteKey(parent_key, subkey_name)
                return True, f"已删除 IFEO 子键: {subkey_name}"
                
        except PermissionError:
            return False, "权限不足，请以管理员身份运行"
        except FileNotFoundError:
            return False, "IFEO 注册表项不存在"
        except OSError as e:
            return False, f"删除 IFEO 条目失败: {e}"
    
    def _delete_boot_execute_entry(self, entry: AutorunEntry) -> tuple:
        """
        从 BootExecute REG_MULTI_SZ 中移除指定条目
        
        BootExecute 位于:
        HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\BootExecute
        
        这是一个 REG_MULTI_SZ 值，包含系统启动时执行的命令列表
        """
        import winreg
        
        BOOTEXECUTE_KEY_PATH = r'SYSTEM\CurrentControlSet\Control\Session Manager'
        VALUE_NAME = 'BootExecute'
        
        target_string = entry.entry or entry.launch_string or ''
        if not target_string:
            return False, "无法确定要移除的条目内容"
        
        print(f"[Parser] _delete_boot_execute_entry: target={target_string}")
        
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, BOOTEXECUTE_KEY_PATH, 0,
                               winreg.KEY_SET_VALUE | winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                try:
                    current_value, value_type = winreg.QueryValueEx(key, VALUE_NAME)
                except FileNotFoundError:
                    return False, "BootExecute 值不存在"
                
                if value_type != winreg.REG_MULTI_SZ:
                    return False, f"期望 REG_MULTI_SZ 类型，实际为 {value_type}"
                
                if target_string not in current_value:
                    return False, f"目标条目不在 BootExecute 中"
                
                updated_value = [item for item in current_value if item != target_string]
                
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_MULTI_SZ, updated_value)
                
                return True, f"已从 BootExecute 中移除: {target_string}"
                
        except PermissionError:
            return False, "权限不足，请以管理员身份运行"
        except FileNotFoundError:
            return False, "Session Manager 键不存在"
        except OSError as e:
            return False, f"编辑 BootExecute 失败: {e}"
    
    def _delete_appinit_dlls_entry(self, entry: AutorunEntry) -> tuple:
        """
        从 AppInit_DLLs REG_SZ 中移除指定 DLL
        
        AppInit_DLLs 位于:
        HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows\AppInit_DLLs
        HKLM\SOFTWARE\Wow6432Node\Microsoft\Windows NT\CurrentVersion\Windows\AppInit_DLLs (32-bit)
        
        这是一个 REG_SZ 值，包含空格分隔的 DLL 路径列表
        """
        import winreg
        
        target_dll = entry.entry or entry.launch_string or ''
        if not target_dll:
            return False, "无法确定要移除的 DLL"
        
        print(f"[Parser] _delete_appinit_dlls_entry: target={target_dll}")
        
        root, key_path = self._parse_location(entry.location)
        if root is None:
            return False, f"无法解析注册表路径: {entry.location}"
        
        VALUE_NAME = 'AppInit_DLLs'
        
        try:
            with winreg.OpenKey(root, key_path, 0,
                               winreg.KEY_SET_VALUE | winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                try:
                    current_value, value_type = winreg.QueryValueEx(key, VALUE_NAME)
                except FileNotFoundError:
                    return False, "AppInit_DLLs 值不存在"
                
                if value_type != winreg.REG_SZ:
                    return False, f"期望 REG_SZ 类型，实际为 {value_type}"
                
                # 分割 DLL 列表（空格分隔）
                dll_list = current_value.split() if current_value else []
                
                if target_dll not in dll_list:
                    return False, f"目标 DLL 不在 AppInit_DLLs 中"
                
                # 移除指定 DLL
                updated_list = [dll for dll in dll_list if dll != target_dll]
                updated_value = ' '.join(updated_list)
                
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, updated_value)
                
                return True, f"已从 AppInit_DLLs 中移除: {target_dll}"
                
        except PermissionError:
            return False, "权限不足，请以管理员身份运行"
        except FileNotFoundError:
            return False, "Windows 键不存在"
        except OSError as e:
            return False, f"编辑 AppInit_DLLs 失败: {e}"
    
    def _delete_scheduled_task(self, entry: AutorunEntry) -> tuple:
        """删除计划任务"""
        cmd = ['schtasks', '/delete', '/tn', entry.entry, '/f']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return False, "操作超时(30s)，计划任务可能需要管理员权限或在远程计算机上"
        
        if result.returncode == 0:
            return True, f"已删除计划任务: {entry.entry}"
        else:
            error_msg = result.stderr.strip() if result.stderr.strip() else f"返回码: {result.returncode}"
            return False, error_msg
    
    def _delete_service(self, entry: AutorunEntry) -> tuple:
        """删除服务"""
        print(f"[Parser] _delete_service 开始")
        print(f"[Parser] entry.service_name: {entry.service_name}")
        
        if not entry.service_name:
            print(f"[Parser] service_name 为空，无法删除")
            return False, "Service name not available, cannot delete"
        
        cmd = ['sc', 'delete', entry.service_name]
        print(f"[Parser] 执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print(f"[Parser] 命令返回码: {result.returncode}")
        print(f"[Parser] 命令输出: {result.stdout}")
        print(f"[Parser] 命令错误: {result.stderr}")
        
        if result.returncode == 0:
            return True, f"已删除服务: {entry.service_name}"
        else:
            return False, result.stderr
    
    def calculate_file_hash(self, file_path: str) -> dict:
        """手动计算文件hash"""
        if not os.path.exists(file_path):
            return {'md5': 'N/A', 'sha256': 'N/A'}
        
        try:
            md5 = hashlib.md5()
            sha256 = hashlib.sha256()
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    md5.update(chunk)
                    sha256.update(chunk)
            
            return {
                'md5': md5.hexdigest(),
                'sha256': sha256.hexdigest()
            }
        except PermissionError:
            return {'md5': 'Access Denied', 'sha256': 'Access Denied'}
