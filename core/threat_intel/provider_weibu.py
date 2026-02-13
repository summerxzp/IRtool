from .base import IOCQuery, IOCQueryResult, ThreatIntelProvider


class WeibuProvider(ThreatIntelProvider):
    """微步在线情报 provider（占位实现，后续接入真实 HTTP API）。"""

    def __init__(self, api_key: str = "", base_url: str = "https://api.threatbook.cn"):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def name(self) -> str:
        return "weibu"

    def query(self, ioc: IOCQuery, timeout: float = 8.0) -> IOCQueryResult:
        if not self.api_key:
            return self.normalize_error(ioc, "missing_api_key")

        # 占位：后续接入 requests 调用真实接口，并根据 IOCType 路由 endpoint。
        return IOCQueryResult(
            provider=self.name,
            query=ioc,
            success=True,
            verdict="unknown",
            severity="unknown",
            confidence=0.0,
            summary="weibu provider scaffold: API wiring pending",
            raw={
                "ioc": ioc.value,
                "ioc_type": ioc.ioc_type.value,
                "timeout": timeout,
            },
        )
