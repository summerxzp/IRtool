import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional

from .base import IOCQuery, IOCQueryResult, ThreatIntelProvider


class ThreatIntelService:
    """IOC 查询服务：封装多 provider 注册、单条查询与批量查询。"""

    def __init__(self):
        self._providers: Dict[str, ThreatIntelProvider] = {}

    def register_provider(self, provider: ThreatIntelProvider) -> None:
        self._providers[provider.name] = provider

    def get_provider(self, name: str) -> Optional[ThreatIntelProvider]:
        return self._providers.get(name)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())

    def query_one(self, ioc: IOCQuery, provider_name: str, timeout: float = 8.0) -> IOCQueryResult:
        provider = self.get_provider(provider_name)
        if not provider:
            return IOCQueryResult(
                provider=provider_name,
                query=ioc,
                success=False,
                error=f"provider_not_found:{provider_name}",
                summary=f"未找到情报源: {provider_name}",
            )
        try:
            return provider.query(ioc, timeout=timeout)
        except Exception as exc:
            return provider.normalize_error(ioc, str(exc))

    def query_batch(
        self,
        iocs: Iterable[IOCQuery],
        provider_name: str,
        timeout: float = 8.0,
        max_workers: int = 4,
        qps_limit: float = 0.0,
    ) -> List[IOCQueryResult]:
        """批量查询。

        qps_limit:
        - 0 表示不限制。
        - >0 表示每秒请求上限，会在提交任务时做简单节流。
        """
        provider = self.get_provider(provider_name)
        if not provider:
            missing_results = []
            for ioc in iocs:
                missing_results.append(
                    IOCQueryResult(
                        provider=provider_name,
                        query=ioc,
                        success=False,
                        error=f"provider_not_found:{provider_name}",
                        summary=f"未找到情报源: {provider_name}",
                    )
                )
            return missing_results

        items = list(iocs)
        if not items:
            return []

        results: List[IOCQueryResult] = [None] * len(items)  # type: ignore
        submit_interval = (1.0 / qps_limit) if qps_limit and qps_limit > 0 else 0.0
        last_submit = 0.0

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_index = {}
            for idx, ioc in enumerate(items):
                if submit_interval > 0:
                    now = time.monotonic()
                    wait = submit_interval - (now - last_submit)
                    if wait > 0:
                        time.sleep(wait)
                    last_submit = time.monotonic()
                future = pool.submit(self._query_safe, provider, ioc, timeout)
                future_to_index[future] = idx

            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    results[idx] = provider.normalize_error(items[idx], str(exc))

        return results

    @staticmethod
    def _query_safe(provider: ThreatIntelProvider, ioc: IOCQuery, timeout: float) -> IOCQueryResult:
        try:
            return provider.query(ioc, timeout=timeout)
        except Exception as exc:
            return provider.normalize_error(ioc, str(exc))
