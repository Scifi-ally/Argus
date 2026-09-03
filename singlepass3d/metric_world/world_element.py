"""
Spatially-Indexed Persistent Surface Element (Surfel) Store for SinglePass3D.
Maintains continuous world state with dual Voxel-Hash and KD-Tree indexing,
covariance ellipsoids, and multi-hypothesis surface representation.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
import numpy as np
from scipy.spatial import cKDTree

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import (
    ConfidenceLevel,
    Provenance,
    SemanticClass,
    VisibilityState,
    WorldElement,
    WorldElementState,
)


class WorldElementStore:
    """
    Persistent spatial index of WorldElement surfels.
    This class maintains the authoritative geometric state of the reconstructed 3D world.
    Combines O(1) voxel spatial hashing for rapid incremental point integration
    with global cKDTree indexing for batch validation and spatial radius queries.
    """
    def __init__(self, voxel_size_m: float = 0.05):
        self.voxel_size_m = voxel_size_m
        self.elements: Dict[int, WorldElement] = {}
        self.logger = get_logger()
        self._next_id: int = 0
        self._kdtree: Optional[cKDTree] = None
        self._tree_dirty: bool = True
        self._index_to_id: List[int] = []
        # Spatial Voxel Grid Hash: (gx, gy, gz) -> list of element_ids
        self._voxel_grid: Dict[Tuple[int, int, int], List[int]] = {}

    def __len__(self) -> int:
        return len(self.elements)

    def _pos_to_voxel(self, pos: np.ndarray) -> Tuple[int, int, int]:
        gx = int(np.floor(pos[0] / self.voxel_size_m))
        gy = int(np.floor(pos[1] / self.voxel_size_m))
        gz = int(np.floor(pos[2] / self.voxel_size_m))
        return (gx, gy, gz)

    def add_element(self, element: WorldElement) -> int:
        eid = element.element_id
        if eid < 0:
            eid = self._next_id
            element.element_id = eid
            self._next_id += 1
        else:
            self._next_id = max(self._next_id, eid + 1)
            
        self.elements[eid] = element
        self._tree_dirty = True
        
        # Add to voxel hash
        vox = self._pos_to_voxel(element.position)
        if vox not in self._voxel_grid:
            self._voxel_grid[vox] = []
        self._voxel_grid[vox].append(eid)
        return eid

    def remove_element(self, element_id: int) -> None:
        if element_id in self.elements:
            elem = self.elements[element_id]
            vox = self._pos_to_voxel(elem.position)
            if vox in self._voxel_grid and element_id in self._voxel_grid[vox]:
                self._voxel_grid[vox].remove(element_id)
            del self.elements[element_id]
            self._tree_dirty = True

    def get_element(self, element_id: int) -> Optional[WorldElement]:
        return self.elements.get(element_id)

    def query_radius_voxel(
        self,
        query_pos: np.ndarray,
        radius: float,
        query_normal: Optional[np.ndarray] = None,
        max_normal_angle_deg: float = 40.0
    ) -> List[Tuple[WorldElement, float]]:
        """
        Fast O(1) voxel neighborhood lookup (searches neighboring 27 voxels).
        """
        gx, gy, gz = self._pos_to_voxel(query_pos)
        r_vox = max(1, int(np.ceil(radius / self.voxel_size_m)))
        
        results: List[Tuple[WorldElement, float]] = []
        cos_thresh = np.cos(np.radians(max_normal_angle_deg)) if query_normal is not None else -1.0
        
        for dx in range(-r_vox, r_vox + 1):
            for dy in range(-r_vox, r_vox + 1):
                for dz in range(-r_vox, r_vox + 1):
                    key = (gx + dx, gy + dy, gz + dz)
                    eids = self._voxel_grid.get(key)
                    if not eids:
                        continue
                    for eid in eids:
                        elem = self.elements.get(eid)
                        if elem is None or elem.state == WorldElementState.REJECTED:
                            continue
                        dist = float(np.linalg.norm(elem.position - query_pos))
                        if dist <= radius:
                            if query_normal is not None:
                                dot = float(np.dot(elem.normal, query_normal))
                                if dot < cos_thresh:
                                    continue
                            results.append((elem, dist))
        return results

    def _rebuild_index_if_needed(self) -> None:
        if not self._tree_dirty and self._kdtree is not None:
            return
            
        if not self.elements:
            self._kdtree = None
            self._index_to_id = []
            self._tree_dirty = False
            return
            
        active_ids = [eid for eid, elem in self.elements.items() if elem.state != WorldElementState.REJECTED]
        if not active_ids:
            self._kdtree = None
            self._index_to_id = []
            self._tree_dirty = False
            return
            
        positions = np.array([self.elements[eid].position for eid in active_ids], dtype=np.float64)
        self._kdtree = cKDTree(positions)
        self._index_to_id = active_ids
        self._tree_dirty = False

    def query_radius(
        self,
        query_pos: np.ndarray,
        radius: float,
        query_normal: Optional[np.ndarray] = None,
        max_normal_angle_deg: float = 40.0
    ) -> List[Tuple[WorldElement, float]]:
        """
        Finds all active world elements within radius.
        Uses fast voxel search if available.
        """
        return self.query_radius_voxel(
            query_pos=query_pos,
            radius=radius,
            query_normal=query_normal,
            max_normal_angle_deg=max_normal_angle_deg
        )

    def query_nearest(self, query_pos: np.ndarray) -> Optional[Tuple[WorldElement, float]]:
        """
        Finds the single nearest world element to query_pos.
        """
        # Check nearby voxels first
        candidates = self.query_radius_voxel(query_pos, radius=self.voxel_size_m * 3.0)
        if candidates:
            return min(candidates, key=lambda x: x[1])
            
        self._rebuild_index_if_needed()
        if self._kdtree is None or len(self._index_to_id) == 0:
            return None
            
        dist, idx = self._kdtree.query(query_pos, k=1)
        if idx >= len(self._index_to_id):
            return None
        eid = self._index_to_id[idx]
        return self.elements[eid], float(dist)

    def get_all_positions(self) -> np.ndarray:
        if not self.elements:
            return np.empty((0, 3), dtype=np.float64)
        return np.array([elem.position for elem in self.elements.values()], dtype=np.float64)

    def get_all_normals(self) -> np.ndarray:
        if not self.elements:
            return np.empty((0, 3), dtype=np.float64)
        return np.array([elem.normal for elem in self.elements.values()], dtype=np.float64)

    def get_all_colors(self) -> np.ndarray:
        if not self.elements:
            return np.empty((0, 3), dtype=np.float64)
        return np.array([elem.color for elem in self.elements.values()], dtype=np.float64)

    def get_provenance_counts(self) -> Dict[str, int]:
        counts = {p.value: 0 for p in Provenance}
        for elem in self.elements.values():
            counts[elem.provenance.value] = counts.get(elem.provenance.value, 0) + 1
        return counts

    def get_confidence_counts(self) -> Dict[str, int]:
        counts = {c.value: 0 for c in ConfidenceLevel}
        for elem in self.elements.values():
            counts[elem.confidence_level.value] = counts.get(elem.confidence_level.value, 0) + 1
        return counts
