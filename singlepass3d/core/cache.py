"""
Stage checkpointing, caching, and resumption system for SinglePass3D.
"""

from __future__ import annotations
import hashlib
import json
import pickle
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class PipelineCache:
    """
    Manages caching of intermediate stage results to disk.
    Enables resuming interrupted pipelines and skipping unchanged stages.
    """
    def __init__(self, cache_dir: str | Path, enabled: bool = True):
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._meta_file = self.cache_dir / "cache_manifest.json"
            self._manifest: Dict[str, Any] = self._load_manifest()
        else:
            self._manifest = {}

    def _load_manifest(self) -> Dict[str, Any]:
        if self._meta_file.exists():
            try:
                with open(self._meta_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_manifest(self) -> None:
        if not self.enabled:
            return
        with open(self._meta_file, "w", encoding="utf-8") as f:
            json.dump(self._manifest, f, indent=2)

    def _compute_key_hash(self, stage_name: str, config_dict: Optional[Dict[str, Any]] = None, inputs_summary: Optional[str] = None) -> str:
        h = hashlib.sha256()
        h.update(stage_name.encode("utf-8"))
        if config_dict:
            h.update(json.dumps(config_dict, sort_keys=True).encode("utf-8"))
        if inputs_summary:
            h.update(inputs_summary.encode("utf-8"))
        return h.hexdigest()[:16]

    def has_stage(self, stage_name: str, stage_hash: Optional[str] = None) -> bool:
        if not self.enabled:
            return False
        stage_entry = self._manifest.get(stage_name)
        if not stage_entry:
            return False
        if stage_hash and stage_entry.get("hash") != stage_hash:
            return False
        data_file = self.cache_dir / f"{stage_name}.pkl"
        return data_file.exists()

    def get_stage(self, stage_name: str) -> Optional[Any]:
        if not self.enabled or not self.has_stage(stage_name):
            return None
        data_file = self.cache_dir / f"{stage_name}.pkl"
        try:
            with open(data_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def put_stage(self, stage_name: str, data: Any, stage_hash: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return
        data_file = self.cache_dir / f"{stage_name}.pkl"
        try:
            with open(data_file, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            self._manifest[stage_name] = {
                "hash": stage_hash or "",
                "file": data_file.name,
                "metadata": metadata or {},
            }
            self._save_manifest()
        except Exception as e:
            # If caching fails, don't crash the pipeline, but log warning
            pass

    def run_cached(self, stage_name: str, compute_fn: Callable[[], Any], config_dict: Optional[Dict[str, Any]] = None, inputs_summary: Optional[str] = None) -> Any:
        stage_hash = self._compute_key_hash(stage_name, config_dict, inputs_summary)
        if self.has_stage(stage_name, stage_hash):
            cached_data = self.get_stage(stage_name)
            if cached_data is not None:
                return cached_data
        
        result = compute_fn()
        self.put_stage(stage_name, result, stage_hash=stage_hash)
        return result

    def clear(self) -> None:
        if not self.enabled or not self.cache_dir.exists():
            return
        for item in self.cache_dir.glob("*.pkl"):
            try:
                item.unlink()
            except Exception:
                pass
        self._manifest.clear()
        self._save_manifest()
