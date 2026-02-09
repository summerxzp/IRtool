from enum import Enum
from typing import Optional, Dict, Any


class ResultType(Enum):
    """搜索结果类型"""
    AUTORUN = "autorun"
    IP_MATCH = "ip_match"


class SearchResult:
    """统一的搜索结果模型"""
    
    def __init__(
        self,
        result_type: ResultType,
        summary: str,
        source: str,
        detail: Dict[str, Any],
        matched_value: str = "",
        related_entry: Optional[Dict[str, Any]] = None
    ):
        self.result_type = result_type
        self.summary = summary
        self.source = source
        self.detail = detail
        self.matched_value = matched_value
        self.related_entry = related_entry
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'result_type': self.result_type.value,
            'summary': self.summary,
            'source': self.source,
            'detail': self.detail,
            'matched_value': self.matched_value,
            'related_entry': self.related_entry
        }
