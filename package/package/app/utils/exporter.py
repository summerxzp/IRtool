# utils/exporter.py
import csv
import json
from datetime import datetime
from typing import List, Dict
from pathlib import Path

class DataExporter:
    """数据导出工具"""
    
    @staticmethod
    def export_csv(data: List[dict], file_path: str, columns: List[str] = None):
        """导出为CSV"""
        if not data:
            return False, "没有数据可导出"
        
        if columns is None:
            columns = list(data[0].keys())
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(data)
            return True, f"已导出至: {file_path}"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def export_json(data: List[dict], file_path: str):
        """导出为JSON"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, f"已导出至: {file_path}"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def export_html_report(
        network_data: List[dict],
        autoruns_data: List[dict],
        threat_matches: Dict,
        file_path: str
    ):
        """导出HTML报告"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html_template = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>终端安全扫描报告 - {timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .high {{ background-color: #ffcccc; }}
        .medium {{ background-color: #fff3cd; }}
        h2 {{ color: #333; border-bottom: 2px solid #4CAF50; }}
    </style>
</head>
<body>
    <h1>终端安全扫描报告</h1>
    <p>生成时间: {timestamp}</p>
    
    <h2>网络连接 ({len(network_data)} 条)</h2>
    <!-- 网络表格 -->
    
    <h2>自启动项 ({len(autoruns_data)} 条)</h2>
    <!-- 自启动表格 -->
    
    <h2>威胁匹配</h2>
    <!-- 威胁匹配 -->
</body>
</html>
'''
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_template)
            return True, f"报告已生成: {file_path}"
        except Exception as e:
            return False, str(e)