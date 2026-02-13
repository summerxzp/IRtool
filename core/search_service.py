from dataclasses import dataclass
from typing import List, Dict, Any

from utils.search_result import SearchResult, ResultType


@dataclass
class SearchResults:
    mode: str  # "keyword" only (IP direct search removed)
    results: List[SearchResult]
    query: str


class SearchService:
    """Search service for workspace aggregation."""

    def __init__(self, data_store=None):
        self.data_store = data_store

    def get_autoruns_entries(self) -> List[Dict[str, Any]]:
        if not self.data_store:
            return []
        entries = self.data_store.get_autoruns_entries() or []
        return [self._normalize_entry(e) for e in entries]

    def get_network_connections(self) -> List[Dict[str, Any]]:
        if not self.data_store:
            return []
        return self.data_store.get_network_connections() or []

    def has_autoruns_data(self) -> bool:
        return len(self.get_autoruns_entries()) > 0

    def has_network_data(self) -> bool:
        return len(self.get_network_connections()) > 0

    def search(self, text: str) -> SearchResults:
        """搜索功能 - 仅支持关键字搜索，IP 搜索已通过规则扫描实现
        
        注意: 搜索框不再接受 IP 字符串进行直接搜索。
        IP 的发现与定位全部通过【规则扫描】完成。
        """
        text = (text or "").strip()
        if not text:
            return SearchResults(mode="keyword", results=[], query=text)

        keyword = text.lower()
        results = self._search_autoruns_by_keyword(keyword)
        return SearchResults(mode="keyword", results=results, query=text)

    def _normalize_entry(self, entry: Any) -> Dict[str, Any]:
        if isinstance(entry, dict):
            entry_dict = entry.copy()
        elif hasattr(entry, "to_dict"):
            entry_dict = entry.to_dict()
        else:
            entry_dict = {
                "entry": getattr(entry, "entry", ""),
                "description": getattr(entry, "description", ""),
                "publisher": getattr(entry, "publisher", ""),
                "company": getattr(entry, "company", ""),
                "image_path": getattr(entry, "image_path", ""),
                "timestamp": getattr(entry, "timestamp", ""),
                "category": getattr(entry, "category", ""),
                "location": getattr(entry, "location", ""),
                "enabled": getattr(entry, "enabled", ""),
                "signer_status": getattr(entry, "signer_status", ""),
                "launch_string": getattr(entry, "launch_string", ""),
                "command_line": getattr(entry, "command_line", ""),
                "signature_detail": getattr(entry, "signature_detail", ""),
                "sha256": getattr(entry, "sha256", ""),
                "file_size": getattr(entry, "file_size", ""),
                "file_version": getattr(entry, "file_version", ""),
                "service_name": getattr(entry, "service_name", ""),
                "file_exists": getattr(entry, "file_exists", True),
            }
            detail_data = getattr(entry, "detail_data", None)
            if isinstance(detail_data, dict):
                entry_dict["detail_data"] = detail_data

        if not entry_dict.get("command_line"):
            entry_dict["command_line"] = entry_dict.get("launch_string", "")

        return entry_dict

    def _get_entry_field_value(self, entry: Dict[str, Any], key: str) -> str:
        value = entry.get(key)
        if value:
            return str(value)
        detail = entry.get("detail_data")
        if isinstance(detail, dict):
            value = detail.get(key)
            if value:
                return str(value)
        return ""

    def _get_entry_command_line(self, entry: Dict[str, Any]) -> str:
        value = self._get_entry_field_value(entry, "command_line")
        if not value:
            value = self._get_entry_field_value(entry, "launch_string")
        return value

    def _search_autoruns_by_keyword(self, keyword: str) -> List[SearchResult]:
        results: List[SearchResult] = []
        for entry in self.get_autoruns_entries():
            search_fields = [
                self._get_entry_field_value(entry, "entry"),
                self._get_entry_field_value(entry, "description"),
                self._get_entry_field_value(entry, "publisher"),
                self._get_entry_field_value(entry, "image_path"),
                self._get_entry_command_line(entry),
            ]
            if any(keyword in field.lower() for field in search_fields if field):
                summary = f"Autorun 项 {entry.get('entry', 'Unknown')} 命中关键字"
                result = SearchResult(
                    result_type=ResultType.AUTORUN,
                    summary=summary,
                    source="keyword",
                    detail={"entry": entry, "kind": "autorun"},
                    matched_value=keyword,
                    related_entry=entry,
                )
                results.append(result)
        return results

    # 注意: 直接 IP 搜索功能已移除
    # IP 的发现与定位全部通过【规则扫描】完成
    # 保留以下方法供规则引擎内部使用
