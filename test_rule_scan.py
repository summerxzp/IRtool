"""
规则扫描功能测试脚本
用于验证银狐病毒案例的持久化条目检测
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.rule_engine import RuleEngine
from core.autoruns_parser import AutorunEntry


def create_test_entries():
    """创建测试用的持久化条目"""
    entries = []
    
    # ========== 测试1: 银狐 Services 持久化 - 路径匹配 ==========
    entry1 = AutorunEntry(
        location="Services",
        entry="QIpqUotP",
        enabled="enabled",
        category="Service",
        description="",
        publisher="",
        company="",
        image_path="C:\\jnetpub\\wwwroot\\9J1puF\\nBXrwBPO\\EXWv1QXoIGz.exe",
        launch_string='cmd /c cd /d "C:\\jnetpub\\wwwroot\\9J1puF\\nBXrwBPO\\" && start "" "C:\\jnetpub\\wwwroot\\9J1puF\\nBXrwBPO\\EXWv1QXoIGz.exe"',
        timestamp="",
        md5="",
        sha256="",
        signer="",
        signer_status="Not Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="QIpqUotP",
        file_exists=True
    )
    entries.append(("银狐-Services持久化(路径匹配)", entry1))
    
    # ========== 测试2: 银狐 任务计划 - rundll32混淆 ==========
    entry2 = AutorunEntry(
        location="Task Scheduler",
        entry="BitLocker MDM policy",
        enabled="enabled",
        category="Task",
        description="BitLocker MDM policy refresh",
        publisher="",
        company="",
        image_path="C:\\Windows\\System32\\rundll32.exe",
        launch_string='r""u""n""d""ll""32.exe "C:\\Program Files\\Windows Media Player\\Music.dll" Music',
        timestamp="",
        md5="",
        sha256="",
        signer="Microsoft Windows",
        signer_status="Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="",
        file_exists=True
    )
    entries.append(("银狐-任务计划(rundll32混淆1)", entry2))
    
    # ========== 测试3: 银狐 任务计划 - rundll32混淆2 ==========
    entry3 = AutorunEntry(
        location="Task Scheduler",
        entry="BitLocker Encrypt All",
        enabled="enabled",
        category="Task",
        description="BitLocker Encrypt All Drives",
        publisher="",
        company="",
        image_path="C:\\Windows\\System32\\rundll32.exe",
        launch_string='r""u""n""d""ll""32.exe "C:\\Program Files\\Windows Mail\\wab.dll" Intel acc',
        timestamp="",
        md5="",
        sha256="",
        signer="Microsoft Windows",
        signer_status="Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="",
        file_exists=True
    )
    entries.append(("银狐-任务计划(rundll32混淆2)", entry3))
    
    # ========== 测试4: 银狐 inetpub 路径 ==========
    entry4 = AutorunEntry(
        location="Services",
        entry="TestService",
        enabled="enabled",
        category="Service",
        description="",
        publisher="",
        company="",
        image_path="C:\\inetpub\\wwwroot\\test\\malware.exe",
        launch_string="C:\\inetpub\\wwwroot\\test\\malware.exe",
        timestamp="",
        md5="",
        sha256="",
        signer="",
        signer_status="Not Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="TestService",
        file_exists=True
    )
    entries.append(("银狐-inetpub路径测试", entry4))
    
    # ========== 测试5: IP地址匹配测试 ==========
    entry5 = AutorunEntry(
        location="Logon",
        entry="TestIP",
        enabled="enabled",
        category="Logon",
        description="",
        publisher="",
        company="",
        image_path="C:\\Windows\\System32\\test.exe",
        launch_string='C:\\Windows\\System32\\test.exe --connect 223.5.5.5:8080',
        timestamp="",
        md5="",
        sha256="",
        signer="",
        signer_status="Not Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="",
        file_exists=True
    )
    entries.append(("IP地址匹配测试(223.5.5.5)", entry5))
    
    # ========== 测试6: SHA256 Hash匹配测试 ==========
    entry6 = AutorunEntry(
        location="Logon",
        entry="TestHash",
        enabled="enabled",
        category="Logon",
        description="",
        publisher="",
        company="",
        image_path="C:\\Windows\\System32\\test.exe",
        launch_string="C:\\Windows\\System32\\test.exe",
        timestamp="",
        md5="",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        signer="",
        signer_status="Not Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="",
        file_exists=True
    )
    entries.append(("SHA256 Hash匹配测试", entry6))
    
    # ========== 测试7: MD5 Hash匹配测试 ==========
    entry7 = AutorunEntry(
        location="Logon",
        entry="TestMD5",
        enabled="enabled",
        category="Logon",
        description="",
        publisher="",
        company="",
        image_path="C:\\Windows\\System32\\test.exe",
        launch_string="C:\\Windows\\System32\\test.exe",
        timestamp="",
        md5="5d41402abc4b2a76b9719d911017c592",
        sha256="",
        signer="",
        signer_status="Not Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="",
        file_exists=True
    )
    entries.append(("MD5 Hash匹配测试", entry7))
    
    # ========== 测试8: PowerShell编码执行测试 ==========
    entry8 = AutorunEntry(
        location="Logon",
        entry="TestPowerShell",
        enabled="enabled",
        category="Logon",
        description="",
        publisher="",
        company="",
        image_path="C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        launch_string='powershell.exe -enc UwB0AGEAcgB0AC0AUwBsAGUAZQBwACAALQBzACAAMQAw',
        timestamp="",
        md5="",
        sha256="",
        signer="Microsoft Windows",
        signer_status="Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="",
        file_exists=True
    )
    entries.append(("PowerShell编码执行测试", entry8))
    
    # ========== 测试9: 正常rundll32调用(应该不匹配银狐规则) ==========
    entry9 = AutorunEntry(
        location="Task Scheduler",
        entry="Normal Task",
        enabled="enabled",
        category="Task",
        description="Normal system task",
        publisher="",
        company="",
        image_path="C:\\Windows\\System32\\rundll32.exe",
        launch_string='C:\\Windows\\System32\\rundll32.exe "C:\\Windows\\System32\\shell32.dll",Control_RunDLL',
        timestamp="",
        md5="",
        sha256="",
        signer="Microsoft Windows",
        signer_status="Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="",
        file_exists=True
    )
    entries.append(("正常rundll32调用(应无匹配)", entry9))
    
    # ========== 测试10: jnetpub命令行匹配 ==========
    entry10 = AutorunEntry(
        location="Logon",
        entry="TestJnetpubCmd",
        enabled="enabled",
        category="Logon",
        description="",
        publisher="",
        company="",
        image_path="C:\\Windows\\System32\\cmd.exe",
        launch_string='cmd.exe /c "C:\\jnetpub\\wwwroot\\test\\script.bat"',
        timestamp="",
        md5="",
        sha256="",
        signer="Microsoft Windows",
        signer_status="Verified",
        signature_detail="",
        file_size="",
        file_version="",
        service_name="",
        file_exists=True
    )
    entries.append(("银狐-jnetpub命令行匹配", entry10))
    
    return entries


def test_rule_scan():
    """测试规则扫描功能"""
    print("=" * 80)
    print("规则扫描功能测试")
    print("=" * 80)
    print()
    
    # 初始化规则引擎 - 使用测试规则文件
    test_rules_path = r"d:\project\IRtool\data\test_rules.json"
    rule_engine = RuleEngine(rules_path=test_rules_path)
    print(f"已加载 {len(rule_engine.rules)} 条规则 (来自 test_rules.json)")
    print()
    
    # 显示当前规则
    print("-" * 80)
    print("当前规则列表:")
    print("-" * 80)
    for rule in rule_engine.rules:
        match_info = rule.get('match', [{}])[0]
        print(f"  [{rule.get('severity', 'unknown').upper()}] {rule.get('family', 'unknown')} - {rule.get('id', 'unknown')}")
        print(f"      字段: {match_info.get('field', 'unknown')}, 类型: {match_info.get('type', 'unknown')}")
        print(f"      值: {match_info.get('value', 'unknown')}")
        print(f"      备注: {rule.get('note', '')}")
        print()
    
    # 创建测试条目
    test_entries = create_test_entries()
    
    print("=" * 80)
    print("开始扫描测试条目")
    print("=" * 80)
    print()
    
    matched_count = 0
    unmatched_count = 0
    
    for test_name, entry in test_entries:
        print(f"\n测试: {test_name}")
        print(f"  Location: {entry.location}")
        print(f"  Entry: {entry.entry}")
        print(f"  Image Path: {entry.image_path}")
        print(f"  Launch String: {entry.launch_string[:80]}..." if len(entry.launch_string) > 80 else f"  Launch String: {entry.launch_string}")
        
        # 执行扫描
        matched_rules = rule_engine.scan_entry(entry.to_dict())
        
        if matched_rules:
            matched_count += 1
            print(f"  [MATCHED] 命中 {len(matched_rules)} 条规则:")
            for rule in matched_rules:
                match_info = rule.get('match', [{}])[0]
                print(f"    - [{rule.get('severity', 'unknown').upper()}] {rule.get('family', 'unknown')}: {rule.get('id', 'unknown')}")
                print(f"      匹配字段: {match_info.get('field', 'unknown')}")
                print(f"      匹配类型: {match_info.get('type', 'unknown')}")
                print(f"      匹配值: {match_info.get('value', 'unknown')}")
                print(f"      备注: {rule.get('note', '')}")
        else:
            unmatched_count += 1
            print(f"  [NO MATCH] 未命中任何规则")
    
    print()
    print("=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    print(f"总测试条目: {len(test_entries)}")
    print(f"命中规则: {matched_count}")
    print(f"未命中: {unmatched_count}")
    print()
    
    # 按规则类型统计
    print("-" * 80)
    print("规则类型统计:")
    print("-" * 80)
    type_stats = {}
    for test_name, entry in test_entries:
        matched_rules = rule_engine.scan_entry(entry.to_dict())
        for rule in matched_rules:
            rule_types = rule_engine._rule_types(rule)
            for t in rule_types:
                type_stats[t] = type_stats.get(t, 0) + 1
    
    for rule_type, count in sorted(type_stats.items()):
        print(f"  {rule_type}: {count} 次匹配")
    
    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_rule_scan()
