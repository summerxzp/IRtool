# utils/exporter.py
import csv
import json
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