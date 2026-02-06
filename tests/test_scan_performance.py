import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
from core.autoruns_parser import AutorunsParser

def test_scan_performance():
    """测试扫描性能"""
    print("[*] 初始化 AutorunsParser...")
    parser = AutorunsParser()
    
    print("[*] 开始扫描（默认参数，不计算hash，不验证签名）...")
    start_time = time.time()
    
    try:
        entries = parser.scan(
            include_hash=False,
            verify_signature=False,
            category_filter=None
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"[*] 扫描完成！")
        print(f"[*] 耗时: {elapsed_time:.2f} 秒")
        print(f"[*] 扫描到 {len(entries)} 个条目")
        
        # 统计各类别数量
        category_counts = {}
        for entry in entries:
            category = entry.category
            category_counts[category] = category_counts.get(category, 0) + 1
        
        print(f"[*] 共有 {len(category_counts)} 个类别:")
        for category, count in sorted(category_counts.items()):
            print(f"    - {category}: {count} 个条目")
        
        # 检查性能
        if elapsed_time <= 30:
            print(f"[✓] 性能测试通过！扫描时间 {elapsed_time:.2f} 秒 ≤ 30 秒")
        else:
            print(f"[✗] 性能测试失败！扫描时间 {elapsed_time:.2f} 秒 > 30 秒")
        
        return elapsed_time <= 30
        
    except Exception as e:
        print(f"[✗] 扫描失败: {e}")
        return False

if __name__ == "__main__":
    test_scan_performance()
