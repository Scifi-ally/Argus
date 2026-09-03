"""
Structured logging and diagnostics tracking for SinglePass3D.
"""

from __future__ import annotations
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class SinglePass3DLogger:
    """
    Console and JSON structured event logger with stage tracking.
    """
    def __init__(self, name: str = "SinglePass3D", log_file: Optional[str | Path] = None, verbosity: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(verbosity)
        self.logger.handlers.clear()
        
        # Console Formatter
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setLevel(verbosity)
        c_format = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%H:%M:%S")
        c_handler.setFormatter(c_format)
        self.logger.addHandler(c_handler)
        
        # Diagnostics and structured events store
        self.events: List[Dict[str, Any]] = []
        self.stage_timings: Dict[str, float] = {}
        self._current_stage: Optional[str] = None
        self._stage_start_time: Optional[float] = None
        self.log_file = Path(log_file) if log_file else None
        
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            f_handler = logging.FileHandler(str(self.log_file), mode="w", encoding="utf-8")
            f_handler.setLevel(logging.DEBUG)
            f_format = logging.Formatter("%(asctime)s\t%(levelname)s\t%(message)s")
            f_handler.setFormatter(f_format)
            self.logger.addHandler(f_handler)

    def start_stage(self, stage_number: int, stage_name: str, description: str = "") -> None:
        """Mark start of an architectural stage."""
        if self._current_stage and self._stage_start_time is not None:
            self.end_stage(self._current_stage)
            
        stage_key = f"Stage_{stage_number:02d}_{stage_name}"
        self._current_stage = stage_key
        self._stage_start_time = time.perf_counter()
        
        msg = f"=== Stage {stage_number}/25: {stage_name} ==="
        if description:
            msg += f" ({description})"
        self.logger.info(msg)
        
        self.events.append({
            "type": "stage_start",
            "stage_number": stage_number,
            "stage_name": stage_name,
            "timestamp": time.time(),
            "description": description
        })

    def end_stage(self, stage_name: Optional[str] = None, status: str = "SUCCESS", details: Optional[Dict[str, Any]] = None) -> None:
        """Mark completion of an architectural stage."""
        stage_key = stage_name or self._current_stage or "unknown_stage"
        elapsed = 0.0
        if self._stage_start_time is not None:
            elapsed = time.perf_counter() - self._stage_start_time
            self.stage_timings[stage_key] = elapsed
            self._stage_start_time = None
            
        self.logger.info(f"--- Completed {stage_key} in {elapsed:.2f}s [Status: {status}] ---")
        
        self.events.append({
            "type": "stage_end",
            "stage_key": stage_key,
            "status": status,
            "duration_seconds": elapsed,
            "timestamp": time.time(),
            "details": details or {}
        })
        self._current_stage = None

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(msg)
        if kwargs:
            self.events.append({"type": "info", "msg": msg, "data": kwargs, "timestamp": time.time()})

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(msg)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(msg)
        self.events.append({"type": "warning", "msg": msg, "data": kwargs, "timestamp": time.time()})

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(msg)
        self.events.append({"type": "error", "msg": msg, "data": kwargs, "timestamp": time.time()})

    def record_metric(self, name: str, value: Any, unit: str = "") -> None:
        self.events.append({
            "type": "metric",
            "metric_name": name,
            "value": value,
            "unit": unit,
            "timestamp": time.time()
        })

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "total_stages_recorded": len(self.stage_timings),
            "stage_durations": self.stage_timings,
            "total_pipeline_time_seconds": sum(self.stage_timings.values()),
            "events_count": len(self.events),
            "events": self.events
        }

    def export_diagnostics(self, out_path: str | Path) -> None:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.get_diagnostics(), f, indent=2)


_DEFAULT_LOGGER: Optional[SinglePass3DLogger] = None


def get_logger(name: str = "SinglePass3D", log_file: Optional[str | Path] = None) -> SinglePass3DLogger:
    global _DEFAULT_LOGGER
    if _DEFAULT_LOGGER is None:
        _DEFAULT_LOGGER = SinglePass3DLogger(name=name, log_file=log_file)
    return _DEFAULT_LOGGER
