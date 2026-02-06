# core/network_monitor.py
import psutil
from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime
import json
import socket
import platform
import struct


@dataclass
class NetworkConnection:
    """网络连接数据模型"""
    timestamp: str
    pid: int
    process_name: str
    process_path: str
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    status: str
    family: str  # TCP/UDP
    
    def to_dict(self):
        return asdict(self)


class NetworkMonitor:
    """网络监控核心类"""
    
    # 需要监控的连接状态
    VALID_STATUSES = [
        'ESTABLISHED', 'LISTEN', 'TIME_WAIT', 
        'CLOSE_WAIT', 'SYN_SENT', 'SYN_RECV', 'NONE'
    ]
    
    def __init__(self):
        self._process_cache = {}  # PID -> (name, path) 缓存
        # 新增：连接归属缓存
        # Key: (local_ip, local_port, remote_ip, remote_port, protocol_type)
        # Value: process_name
        self._connection_owner_cache = {}
        
    def get_connections(self, status_filter: Optional[List[str]] = None) -> List[NetworkConnection]:
        """获取当前所有网络连接"""
        # 【修复点1】：每次获取连接时强制清空进程缓存，防止PID复用导致的幽灵进程
        self._process_cache.clear()
        
        connections = []
        
        for conn in psutil.net_connections(kind='inet'):
            # 过滤无效连接
            if conn.pid is None:
                continue
                
            # 提取五元组 Key (增加协议类型)
            laddr = (conn.laddr.ip, conn.laddr.port) if conn.laddr else ("", 0)
            raddr = (conn.raddr.ip, conn.raddr.port) if conn.raddr else ("", 0)
            protocol_type = "TCP" if conn.type == socket.SOCK_STREAM else "UDP" if conn.type == socket.SOCK_DGRAM else "UNKNOWN"
            conn_key = (laddr[0], laddr[1], raddr[0], raddr[1], protocol_type)
            
            # 获取进程信息（带缓存）
            proc_name, proc_path = self._get_process_info(conn.pid)
            
            # 状态筛选
            if status_filter and conn.status not in status_filter:
                continue
            
            # 【修复点2】：保留原始值，不再在这里格式化地址
            # local_addr_formatted = self._format_address(laddr[0])
            # remote_addr_formatted = self._format_address(raddr[0]) if raddr[0] else "*"
            
            # 【修复点3】：处理UDP连接状态显示（UDP显示为空，而不是NONE）
            status_for_display = conn.status
            if protocol_type == "UDP" and conn.status == "NONE":
                status_for_display = ""
            
            # 【修复点4】：更新连接归属缓存，使用新的键值结构
            if conn.pid and conn.pid > 0:
                self._connection_owner_cache[conn_key] = {
                    'name': proc_name,
                    'path': proc_path,
                    'pid': conn.pid
                }
            
            # 构建连接对象 - 保留原始值
            nc = NetworkConnection(
                timestamp=datetime.now().strftime("%Y/%m/%d %H:%M:%S"),  # 优化时间格式
                pid=conn.pid if conn.pid else 0,
                process_name=proc_name,
                process_path=proc_path,
                local_address=laddr[0],  # 保留原始值
                local_port=laddr[1],
                remote_address=raddr[0] if raddr[0] else "",  # 保留原始值，UDP可能为"" 
                remote_port=raddr[1] if raddr[0] else 0,  # 使用整数类型，UDP或无远程地址时设为0
                status=status_for_display,
                family=protocol_type  # 显示协议类型 (TCP/UDP) 而不是 IPv4
            )
            connections.append(nc)
            
        return connections
    
    def _get_process_info(self, pid: int) -> tuple:
        """获取进程信息，带缓存，增强异常处理"""
        # 检查缓存
        if pid in self._process_cache:
            return self._process_cache[pid]
        
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            path = proc.exe()
            # 更新缓存
            self._process_cache[pid] = (name, path)
            return name, path
        except psutil.NoSuchProcess:
            # 【修复点5】：进程已结束，返回特殊标记，而不是Unknown
            return "[已结束]", "[已结束]"
        except psutil.AccessDenied:
            # 【修复点6】：权限不足，返回特殊标记
            return "[权限不足]", "[权限不足]"
        except Exception as e:
            # 其他异常情况
            return f"[错误: {str(e)}]", f"[错误: {str(e)}]"
    
    def kill_process(self, pid: int) -> tuple:
        """终止进程"""
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=3)
            return True, f"进程 {pid} 已终止"
        except psutil.NoSuchProcess:
            return False, "进程不存在"
        except psutil.AccessDenied:
            return False, "权限不足，请以管理员身份运行"
        except Exception as e:
            return False, str(e)
    
    def clear_cache(self):
        """清理进程缓存"""
        self._process_cache.clear()

    def close_connection(self, local_address: str, local_port: int, remote_address: str, remote_port: int, protocol: str = "TCP") -> tuple:
        """关闭指定连接（仅支持 Windows TCP/IPv4）"""
        if protocol.upper() != "TCP":
            return False, "仅支持 TCP 连接"
        if not local_address or not remote_address:
            return False, "缺少地址信息"
        if platform.system().lower() != "windows":
            return False, "仅支持 Windows"
        try:
            local_port = int(local_port)
            remote_port = int(remote_port)
        except (TypeError, ValueError):
            return False, "端口无效"
        if local_port <= 0 or remote_port <= 0:
            return False, "端口无效"

        try:
            import ctypes
            class MIB_TCPROW(ctypes.Structure):
                _fields_ = [
                    ("dwState", ctypes.c_ulong),
                    ("dwLocalAddr", ctypes.c_ulong),
                    ("dwLocalPort", ctypes.c_ulong),
                    ("dwRemoteAddr", ctypes.c_ulong),
                    ("dwRemotePort", ctypes.c_ulong),
                ]

            MIB_TCP_STATE_DELETE_TCB = 12

            row = MIB_TCPROW()
            row.dwState = MIB_TCP_STATE_DELETE_TCB
            row.dwLocalAddr = struct.unpack("!I", socket.inet_aton(local_address))[0]
            row.dwRemoteAddr = struct.unpack("!I", socket.inet_aton(remote_address))[0]
            row.dwLocalPort = socket.htons(local_port)
            row.dwRemotePort = socket.htons(remote_port)

            result = ctypes.windll.iphlpapi.SetTcpEntry(ctypes.byref(row))
            if result != 0:
                return False, f"关闭失败: {result}"
            return True, "连接已关闭"
        except OSError as e:
            return False, f"关闭失败: {e}"
        except Exception as e:
            return False, f"关闭失败: {e}"
    
    def stop_monitoring(self):
        """停止监控 - 网络监控无需特殊停止逻辑，只需清理缓存"""
        self.clear_cache()
