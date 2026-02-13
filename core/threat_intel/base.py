from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class IOCType(str, Enum):
    IP = "ip"
    HASH = "hash"
    DOMAIN = "domain"
    URL = "url"


@dataclass
class IOCQuery:
    value: str
    ioc_type: IOCType
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IOCQueryResult:
    provider: str
    query: IOCQuery
    success: bool
    verdict: str = "unknown"
    severity: str = "unknown"
    confidence: float = 0.0
    summary: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


class ThreatIntelProvider(ABC):
    """情报源抽象基类。"""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def query(self, ioc: IOCQuery, timeout: float = 8.0) -> IOCQueryResult:
        raise NotImplementedError

    def normalize_error(self, ioc: IOCQuery, message: str) -> IOCQueryResult:
        return IOCQueryResult(
            provider=self.name,
            query=ioc,
            success=False,
            error=message,
            summary=f"{self.name} 查询失败: {message}",
        )
