from typing import Optional
from backend.infrastructure.worker import DiscoveryWorker

_worker: Optional[DiscoveryWorker] = None


def set_worker(worker: Optional[DiscoveryWorker]):
    global _worker
    _worker = worker


def get_worker() -> Optional[DiscoveryWorker]:
    return _worker
