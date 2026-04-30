# core/network_monitor.py
import psutil
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import json
import socket
import time


@dataclass
class NetworkConnection:
    """网络连接数据模型"""
    timestamp: str
    timestamp_epoch: float
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
        self._process_cache: Dict[int, Tuple[str, str, float]] = {}  # PID -> (name, path, timestamp) 缓存
        self._cache_ttl = 5.0
        
    def get_connections(self, status_filter: Optional[List[str]] = None) -> List[NetworkConnection]:
        """获取当前所有网络连接"""
        self._cleanup_expired_cache()
        
        connections = []
        
        for conn in psutil.net_connections(kind='inet'):
            # 过滤无效连接
            if conn.pid is None:
                continue
                
            # 提取五元组 Key (增加协议类型)
            laddr = (conn.laddr.ip, conn.laddr.port) if conn.laddr else ("", 0)
            raddr = (conn.raddr.ip, conn.raddr.port) if conn.raddr else ("", 0)
            protocol_type = "TCP" if conn.type == socket.SOCK_STREAM else "UDP" if conn.type == socket.SOCK_DGRAM else "UNKNOWN"

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
            
            # 构建连接对象 - 保留原始值
            now = datetime.now()
            nc = NetworkConnection(
                timestamp=now.strftime("%Y/%m/%d %H:%M:%S"),  # 保持现有展示格式
                timestamp_epoch=now.timestamp(),
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
    
    def _cleanup_expired_cache(self):
        """清理过期缓存，防止PID复用问题"""
        now = time.time()
        expired_pids = [
            pid for pid, (_, _, timestamp) in self._process_cache.items()
            if now - timestamp > self._cache_ttl
        ]
        for pid in expired_pids:
            del self._process_cache[pid]
    
    def _get_process_info(self, pid: int) -> tuple:
        """获取进程信息，带TTL缓存，增强异常处理"""
        # 检查缓存及TTL
        if pid in self._process_cache:
            name, path, timestamp = self._process_cache[pid]
            if time.time() - timestamp < self._cache_ttl:
                return name, path
            else:
                # 缓存过期，删除后重新获取
                del self._process_cache[pid]
        
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            path = proc.exe()
            # 更新缓存，带时间戳
            self._process_cache[pid] = (name, path, time.time())
            return name, path
        except psutil.NoSuchProcess:
            # 进程已结束，返回特殊标记
            return "[已结束]", "[已结束]"
        except psutil.AccessDenied:
            # 权限不足，返回特殊标记
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
    
    def stop_monitoring(self):
        """停止监控 - 网络监控无需特殊停止逻辑，只需清理缓存"""
        self.clear_cache()
