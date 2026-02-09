#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Autoruns Tab 重构后的功能
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.autoruns_tab import AutorunsTab
from core.autoruns_parser import AutorunsParser

def test_basic_ui():
    """测试基本 UI 功能"""
    print("=" * 60)
    print("测试 1: 基本 UI 初始化")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    try:
        parser = AutorunsParser()
        tab = AutorunsTab(parser)
        
        # 检查 Detail Pane 是否存在
        assert hasattr(tab, 'detail_pane'), "Detail Pane 不存在"
        print("✓ Detail Pane 已创建")
        
        # 检查 Detail Pane 是否为只读
        assert tab.detail_pane.isReadOnly(), "Detail Pane 应该是只读的"
        print("✓ Detail Pane 是只读的")
        
        # 检查 Detail Pane 是否支持自动换行
        from PyQt6.QtWidgets import QTextEdit
        assert tab.detail_pane.lineWrapMode() == QTextEdit.LineWrapMode.WidgetWidth, "Detail Pane 应该支持自动换行"
        print("✓ Detail Pane 支持自动换行")
        
        # 检查主列表列数
        assert tab.model.columnCount() == 5, f"主列表应该有 5 列，实际有 {tab.model.columnCount()} 列"
        print("✓ 主列表列数正确 (5 列)")
        
        # 检查列标题
        headers = [tab.model.headerData(i, Qt.Orientation.Horizontal) for i in range(5)]
        expected_headers = ['Category', 'Entry', 'Description', 'Publisher', 'Image Path']
        assert headers == expected_headers, f"列标题不匹配: {headers} != {expected_headers}"
        print("✓ 列标题正确")
        
        print("\n测试 1 通过！\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试 1 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_detail_rendering():
    """测试 Detail 渲染功能"""
    print("=" * 60)
    print("测试 2: Detail 渲染功能")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    try:
        parser = AutorunsParser()
        tab = AutorunsTab(parser)
        
        # 测试数据
        test_data = {
            'id': 'test-id-1',
            'entry': 'Test Entry',
            'description': 'Test Description',
            'publisher': 'Test Publisher',
            'company': 'Test Company',
            'image_path': 'C:\\Windows\\System32\\test.exe',
            'timestamp': '2024-01-01 12:00:00',
            'category': 'Logon',
            'enabled': 'Yes',
            'signer_status': '(Verified)',
            'launch_string': 'C:\\Windows\\System32\\test.exe /arg',
            'signature_detail': 'Signed by Test Publisher',
            'sha256': 'a' * 64,
            'file_size': '1024000',
            'file_version': '1.0.0.0',
            'detail_data': {
                "image_path": "C:\\Windows\\System32\\test.exe",
                "command_line": "C:\\Windows\\System32\\test.exe /arg",
                "category": "Logon",
                "timestamp": "2024-01-01 12:00:00",
                "signature": "Verified",
                "publisher": "Test Publisher",
                "company": "Test Company",
                "size": "1024000",
                "version": "1.0.0.0",
                "hash": "a" * 64
            }
        }
        
        # 渲染 Detail
        tab._render_detail(test_data)
        
        # 检查 Detail Pane 内容
        content = tab.detail_pane.toPlainText()
        assert "[Basic]" in content, "Detail 应该包含 [Basic] 分组"
        print("✓ Detail 包含 [Basic] 分组")
        
        assert "[Trust]" in content, "Detail 应该包含 [Trust] 分组"
        print("✓ Detail 包含 [Trust] 分组")
        
        assert "[File]" in content, "Detail 应该包含 [File] 分组"
        print("✓ Detail 包含 [File] 分组")
        
        assert "Image Path" in content, "Detail 应该包含 Image Path 字段"
        print("✓ Detail 包含 Image Path 字段")
        
        assert "Command Line" in content, "Detail 应该包含 Command Line 字段"
        print("✓ Detail 包含 Command Line 字段")
        
        assert "Signature" in content, "Detail 应该包含 Signature 字段"
        print("✓ Detail 包含 Signature 字段")
        
        assert "Hash (SHA256)" in content, "Detail 应该包含 Hash 字段"
        print("✓ Detail 包含 Hash 字段")
        
        print("\n测试 2 通过！\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试 2 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_detail_clear():
    """测试 Detail 清空功能"""
    print("=" * 60)
    print("测试 3: Detail 清空功能")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    try:
        parser = AutorunsParser()
        tab = AutorunsTab(parser)
        
        # 先设置一些内容
        tab.detail_pane.setPlainText("Test content")
        assert tab.detail_pane.toPlainText() == "Test content", "设置内容失败"
        print("✓ Detail Pane 内容已设置")
        
        # 清空内容
        tab.detail_pane.clear()
        assert tab.detail_pane.toPlainText() == "", "清空内容失败"
        print("✓ Detail Pane 内容已清空")
        
        print("\n测试 3 通过！\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试 3 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_model_structure():
    """测试模型结构"""
    print("=" * 60)
    print("测试 4: 模型结构")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    try:
        parser = AutorunsParser()
        tab = AutorunsTab(parser)
        
        # 添加测试数据
        test_entries = [
            {
                'entry': 'Test Entry 1',
                'description': 'Test Description 1',
                'publisher': 'Test Publisher 1',
                'image_path': 'C:\\Windows\\System32\\test1.exe',
                'category': 'Logon',
                'timestamp': '2024-01-01 12:00:00',
                'enabled': 'Yes',
                'signer_status': '(Verified)',
                'launch_string': 'C:\\Windows\\System32\\test1.exe',
                'signature_detail': 'Signed by Test Publisher',
                'sha256': 'a' * 64,
                'file_size': '1024000',
                'file_version': '1.0.0.0'
            }
        ]
        
        tab.model.add_entries(test_entries)
        
        # 检查根节点数量
        assert len(tab.model.root_nodes) == 1, f"应该有 1 个根节点，实际有 {len(tab.model.root_nodes)} 个"
        print("✓ 根节点数量正确")
        
        # 检查根节点是否有子节点
        root_node = tab.model.root_nodes[0]
        assert len(root_node.children) == 0, f"根节点不应该有子节点，实际有 {len(root_node.children)} 个"
        print("✓ 根节点没有子节点（已移除 detail 节点）")
        
        # 检查节点是否有 node_type 属性
        assert not hasattr(root_node, 'node_type'), "节点不应该有 node_type 属性"
        print("✓ 节点没有 node_type 属性（已移除）")
        
        print("\n测试 4 通过！\n")
        return True
        
    except Exception as e:
        print(f"✗ 测试 4 失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("Autoruns Tab 重构功能测试")
    print("=" * 60 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("基本 UI 初始化", test_basic_ui()))
    results.append(("Detail 渲染功能", test_detail_rendering()))
    results.append(("Detail 清空功能", test_detail_clear()))
    results.append(("模型结构", test_model_structure()))
    
    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name:30s} {status}")
    
    print("=" * 60)
    
    # 统计
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！重构成功！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1

if __name__ == '__main__':
    sys.exit(main())
