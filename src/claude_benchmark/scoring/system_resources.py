"""Auto-detect system resources and compute optimal static scoring concurrency."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import psutil

logger = logging.getLogger(__name__)

_CPU_MULTIPLIER = 3
_MEM_PER_WORKER_GB = 0.1
_MIN_WORKERS = 4
_MAX_WORKERS = 32


@dataclass(frozen=True)
class SystemSpecs:
    cpu_count: int
    available_memory_gb: float


def detect_system_specs() -> SystemSpecs:
    cpu_count = psutil.cpu_count(logical=True) or 1
    available_gb = psutil.virtual_memory().available / (1024**3)
    return SystemSpecs(
        cpu_count=cpu_count,
        available_memory_gb=available_gb,
    )


def compute_optimal_static_concurrency(specs: SystemSpecs) -> int:
    cpu_based = int(specs.cpu_count * _CPU_MULTIPLIER)
    mem_based = int(specs.available_memory_gb / _MEM_PER_WORKER_GB)
    return max(_MIN_WORKERS, min(cpu_based, mem_based, _MAX_WORKERS))


def get_auto_static_concurrency() -> int:
    specs = detect_system_specs()
    workers = compute_optimal_static_concurrency(specs)
    logger.info(
        "Auto-detected: %d CPUs, %.1fGB available → %d static workers",
        specs.cpu_count,
        specs.available_memory_gb,
        workers,
    )
    return workers
