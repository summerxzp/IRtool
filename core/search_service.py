from dataclasses import dataclass
from typing import List, Dict, Any
import ipaddress
import re

from utils.search_result import SearchResult, ResultType


@dataclass
class SearchResults:
    mode: str  # "keyword" | "ip"
    results: List[SearchResult]
    query: str
    ip_candidates: List[str]


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
        text = (text or "").strip()
        if not text:
            return SearchResults(mode="keyword", results=[], query=text, ip_candidates=[])

        ip_candidates = self._extract_ip_candidates(text)
        if ip_candidates:
            results: List[SearchResult] = []
            results.extend(self._search_autoruns_by_ip(ip_candidates))
            results.extend(self._search_network_by_ip(ip_candidates))
            return SearchResults(mode="ip", results=results, query=text, ip_candidates=ip_candidates)

        keyword = text.lower()
        results = self._search_autoruns_by_keyword(keyword)
        return SearchResults(mode="keyword", results=results, query=text, ip_candidates=[])

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

    def _search_autoruns_by_ip(self, ip_candidates: List[str]) -> List[SearchResult]:
        results: List[SearchResult] = []
        if not ip_candidates:
            return results

        seen = set()
        for entry in self.get_autoruns_entries():
            search_fields = [
                ("command_line", self._get_entry_command_line(entry)),
                ("image_path", self._get_entry_field_value(entry, "image_path")),
            ]
            entry_key = entry.get("entry", "")
            for ip_address in ip_candidates:
                ip_lower = ip_address.lower()
                for field_name, field_value in search_fields:
                    if not field_value:
                        continue
                    if ip_lower in field_value.lower():
                        dedup_key = (entry_key, ip_address, field_name)
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)

                        summary = f"Autorun 项 {entry.get('entry', 'Unknown')} 命中 IP"
                        result = SearchResult(
                            result_type=ResultType.IP_MATCH,
                            summary=summary,
                            source=field_name,
                            detail={"entry": entry, "kind": "autorun"},
                            matched_value=ip_address,
                            related_entry=entry,
                        )
                        results.append(result)
        return results

    def _search_network_by_ip(self, ip_candidates: List[str]) -> List[SearchResult]:
        results: List[SearchResult] = []
        if not ip_candidates:
            return results

        connections = self.get_network_connections()
        seen = set()
        for conn in connections:
            local_addr = str(conn.get("local_address", ""))
            remote_addr = str(conn.get("remote_address", ""))
            pid = str(conn.get("pid", ""))
            process_name = str(conn.get("process_name", ""))

            search_fields = [
                ("local_address", local_addr),
                ("remote_address", remote_addr),
            ]
            for ip_address in ip_candidates:
                ip_lower = ip_address.lower()
                for field_name, field_value in search_fields:
                    if not field_value:
                        continue
                    if ip_lower in field_value.lower():
                        dedup_key = (pid, local_addr, remote_addr, ip_address, field_name)
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)

                        local_port = conn.get("local_port", "")
                        remote_port = conn.get("remote_port", "")
                        local_display = f"{local_addr}:{local_port}" if local_addr else ""
                        remote_display = f"{remote_addr}:{remote_port}" if remote_addr else ""
                        summary = f"网络连接 PID {pid} {process_name} {local_display} -> {remote_display}"

                        result = SearchResult(
                            result_type=ResultType.IP_MATCH,
                            summary=summary,
                            source=field_name,
                            detail={"connection": conn, "kind": "network"},
                            matched_value=ip_address,
                            related_entry=None,
                        )
                        results.append(result)
        return results

    def _is_ip_address(self, text: str) -> bool:
        try:
            ipaddress.ip_address(text)
            return True
        except ValueError:
            return False

    def _extract_ip_candidates(self, text: str) -> List[str]:
        candidates: List[str] = []
        if not text:
            return candidates

        ipv4_pattern = r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)"
        for match in re.finditer(ipv4_pattern, text):
            ip = match.group(0)
            if self._is_ip_address(ip):
                candidates.append(ip)

        ipv6_bracket_pattern = r"\[([0-9a-fA-F:]+)\]"
        for match in re.finditer(ipv6_bracket_pattern, text):
            ip = match.group(1)
            if self._is_ip_address(ip):
                candidates.append(ip)

        cleaned = text.strip()
        if cleaned:
            if cleaned.count(":") == 1 and cleaned.rsplit(":", 1)[1].isdigit():
                cleaned = cleaned.rsplit(":", 1)[0]
            if cleaned.startswith("[") and "]" in cleaned:
                cleaned = cleaned[1:cleaned.index("]")]
            if self._is_ip_address(cleaned):
                candidates.append(cleaned)

        seen = set()
        unique: List[str] = []
        for ip in candidates:
            if ip not in seen:
                seen.add(ip)
                unique.append(ip)
        return unique
