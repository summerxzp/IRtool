import pytest
from core.network_monitor import NetworkMonitor, NetworkConnection


class TestNetworkMonitor:
    
    def test_get_connections(self):
        monitor = NetworkMonitor()
        connections = monitor.get_connections()
        
        assert isinstance(connections, list)
        
        if connections:
            conn = connections[0]
            assert isinstance(conn, NetworkConnection)
            assert conn.pid > 0
            assert conn.process_name
            # UDP connections have empty status, TCP uses VALID_STATUSES
            if conn.family == "UDP":
                assert conn.status == ""
            else:
                assert conn.status in monitor.VALID_STATUSES
    
    def test_connection_to_dict(self):
        conn = NetworkConnection(
            timestamp="2024-01-01T00:00:00",
            timestamp_epoch=1704067200.0,
            pid=1234,
            process_name="test.exe",
            process_path="C:\\test.exe",
            local_address="127.0.0.1",
            local_port=8080,
            remote_address="192.168.1.1",
            remote_port=443,
            status="ESTABLISHED",
            family="TCP"
        )
        
        data = conn.to_dict()
        assert data['timestamp_epoch'] == 1704067200.0
        assert data['pid'] == 1234
        assert data['process_name'] == "test.exe"
        assert data['status'] == "ESTABLISHED"
        assert data['family'] == "TCP"
    
    def test_status_filter(self):
        monitor = NetworkMonitor()
        connections = monitor.get_connections(status_filter=['ESTABLISHED'])
        
        for conn in connections:
            assert conn.status == 'ESTABLISHED'
    
    def test_process_cache(self):
        monitor = NetworkMonitor()
        monitor.clear_cache()
        
        connections = monitor.get_connections()
        
        if connections:
            assert len(monitor._process_cache) > 0
