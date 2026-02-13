from .base import IOCQuery, IOCQueryResult, ThreatIntelProvider


class VirusTotalProvider(ThreatIntelProvider):
    """VirusTotal provider（占位实现，后续接入真实 API）。"""

    def __init__(self, api_key: str = "", base_url: str = "https://www.virustotal.com/api/v3"):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def name(self) -> str:
        return "virustotal"

    def query(self, ioc: IOCQuery, timeout: float = 8.0) -> IOCQueryResult:
        if not self.api_key:
            return self.normalize_error(ioc, "missing_api_key")

        return IOCQueryResult(
            provider=self.name,
            query=ioc,
            success=True,
            verdict="unknown",
            severity="unknown",
            confidence=0.0,
            summary="virustotal provider scaffold: API wiring pending",
            raw={
                "ioc": ioc.value,
                "ioc_type": ioc.ioc_type.value,
                "timeout": timeout,
            },
        )
