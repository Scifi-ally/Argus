"""
Persistent World Manager and Multi-Observation Fusion Engine for SinglePass3D.
Incrementally accumulates, validates, fuses, and refines the persistent WorldElement state.
Maintains multi-hypothesis surfels and prunes persistent geometric contradictions.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import (
    ConfidenceLevel,
    PointMapResult,
    Pose3D,
    Provenance,
    SemanticClass,
    VisibilityState,
    WorldElement,
    WorldElementState,
)
from singlepass3d.metric_world.local_registration import LocalRegistrationEngine
from singlepass3d.metric_world.world_element import WorldElementStore


class PersistentWorld:
    """
    Central authoritative 3D geometric state manager of SinglePass3D.
    """
    def __init__(
        self,
        voxel_size_m: float = 0.05,
        merge_dist_m: float = 0.08,
        normal_angle_deg: float = 35.0,
        contradiction_loss_rate: float = 0.25
    ):
        self.voxel_size_m = voxel_size_m
        self.merge_dist_m = merge_dist_m
        self.normal_angle_deg = normal_angle_deg
        self.contradiction_loss_rate = contradiction_loss_rate
        
        self.store = WorldElementStore(voxel_size_m=voxel_size_m)
        self.registration_engine = LocalRegistrationEngine()
        self.logger = get_logger()
        
        # Spatial grid hash for fast surfel clustering: (gx, gy, gz) -> List[element_id]
        self._voxel_grid: Dict[Tuple[int, int, int], List[int]] = {}
        # Fusion index at the surfel merge distance. Positions are only moved wholesale
        # by the final ground levelling, which runs after all fusion, so cached cell
        # keys never go stale during a run.
        self._cell_index: Dict[Tuple[int, int, int], List[int]] = {}
        # Hard ceiling on surfel count; a full flight would otherwise allocate tens of
        # millions of Python objects and exhaust memory before meshing.
        self._max_elements: int = 2_000_000

    def _pos_to_voxel(self, pos: np.ndarray) -> Tuple[int, int, int]:
        gx = int(np.floor(pos[0] / self.voxel_size_m))
        gy = int(np.floor(pos[1] / self.voxel_size_m))
        gz = int(np.floor(pos[2] / self.voxel_size_m))
        return (gx, gy, gz)

    def integrate_pointmap(
        self,
        pointmap_res: PointMapResult,
        registered_T: Optional[np.ndarray] = None
    ) -> int:
        """
        Integrates dense observations from a single PointMapResult into the persistent world state.
        Fuses compatible surfels and creates new surfel hypotheses where novel geometry is observed.
        """
        valid_mask = pointmap_res.mask
        if not np.any(valid_mask):
            return 0
            
        pts = pointmap_res.points[valid_mask].reshape(-1, 3)
        normals = pointmap_res.normals[valid_mask].reshape(-1, 3)
        colors = pointmap_res.colors[valid_mask].reshape(-1, 3)
        confs = pointmap_res.confidences[valid_mask].reshape(-1)
        
        # Apply registration transform if provided
        if registered_T is not None and not np.allclose(registered_T, np.eye(4)):
            pts = (registered_T[:3, :3] @ pts.T).T + registered_T[:3, 3]
            normals = (registered_T[:3, :3] @ normals.T).T
            # Re-normalize normals
            norms = np.linalg.norm(normals, axis=1, keepdims=True)
            normals = normals / np.maximum(1e-12, norms)
            
        fid = pointmap_res.frame_id
        cam_pos = pointmap_res.camera_pose.t_wc if pointmap_res.camera_pose else None
        
        # One surfel per merge-distance cell. A dense depth map carries an order of
        # magnitude more points than the surfel spacing can hold, so observations are
        # averaged per cell first and the world state is then touched once per cell
        # instead of once per pixel -- the difference between minutes and hours over a
        # full flight, and between a bounded and an unbounded element count.
        if len(pts) > 60000:
            stride = int(np.ceil(len(pts) / 60000))
            pts = pts[::stride]
            normals = normals[::stride]
            colors = colors[::stride]
            confs = confs[::stride]

        if len(pts) == 0:
            return 0

        cell = max(1e-3, float(self.merge_dist_m))
        gi = np.floor(pts / cell).astype(np.int64)
        uniq, inv = np.unique(gi, axis=0, return_inverse=True)
        inv = np.asarray(inv).ravel()
        M = len(uniq)

        w = np.maximum(1e-3, confs.astype(np.float64))
        wsum = np.bincount(inv, weights=w, minlength=M)
        scale = 1.0 / np.maximum(1e-9, wsum)
        agg_p = np.stack(
            [np.bincount(inv, weights=w * pts[:, c], minlength=M) * scale for c in range(3)], axis=1
        )
        agg_n = np.stack(
            [np.bincount(inv, weights=w * normals[:, c], minlength=M) * scale for c in range(3)], axis=1
        )
        agg_c = np.stack(
            [np.bincount(inv, weights=w * colors[:, c], minlength=M) * scale for c in range(3)], axis=1
        )
        agg_n /= np.maximum(1e-12, np.linalg.norm(agg_n, axis=1, keepdims=True))
        agg_q = np.zeros(M, dtype=np.float64)
        np.maximum.at(agg_q, inv, confs.astype(np.float64))

        if cam_pos is not None:
            rays = agg_p - cam_pos
            rays /= np.maximum(1e-9, np.linalg.norm(rays, axis=1, keepdims=True))
        else:
            rays = -agg_n

        cos_thresh = float(np.cos(np.radians(self.normal_angle_deg)))
        merge_sq = cell * cell
        index = self._cell_index
        elements = self.store.elements
        fused_count = 0
        new_count = 0

        for j in range(M):
            p = agg_p[j]
            n = agg_n[j]
            gx, gy, gz = int(uniq[j, 0]), int(uniq[j, 1]), int(uniq[j, 2])

            # Nearest compatible surfel in the 27 cells around this one: the same
            # neighbourhood the radius query used to scan, reached by dictionary lookup.
            # After the first couple of frames almost every observation lands in a cell
            # that already holds its surfel, so that case is tried on its own first and
            # the surrounding cells are only scanned when it misses.
            best = None
            best_d = merge_sq
            bucket = index.get((gx, gy, gz))
            if bucket:
                for eid in bucket:
                    cand = elements.get(eid)
                    if cand is None:
                        continue
                    diff = cand.position - p
                    d = diff[0] * diff[0] + diff[1] * diff[1] + diff[2] * diff[2]
                    if d >= best_d:
                        continue
                    if cand.normal[0] * n[0] + cand.normal[1] * n[1] + cand.normal[2] * n[2] < cos_thresh:
                        continue
                    best, best_d = cand, d
            if best is None:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            if dx == 0 and dy == 0 and dz == 0:
                                continue
                            bucket = index.get((gx + dx, gy + dy, gz + dz))
                            if not bucket:
                                continue
                            for eid in bucket:
                                cand = elements.get(eid)
                                if cand is None:
                                    continue
                                diff = cand.position - p
                                d = diff[0] * diff[0] + diff[1] * diff[1] + diff[2] * diff[2]
                                if d >= best_d:
                                    continue
                                if cand.normal[0] * n[0] + cand.normal[1] * n[1] + cand.normal[2] * n[2] < cos_thresh:
                                    continue
                                best, best_d = cand, d

            conf = float(agg_q[j])
            if best is not None:
                self._fuse_into(best, p, n, agg_c[j], conf, rays[j], fid)
                fused_count += 1
                continue
            if len(elements) >= self._max_elements:
                continue
            elem = WorldElement(
                element_id=-1,
                position=p.copy(),
                normal=n.copy(),
                covariance=np.eye(3, dtype=np.float64) * (self.merge_dist_m ** 2),
                color=agg_c[j].copy(),
                color_observations=[(fid, agg_c[j].copy())],
                supporting_frames={fid},
                supporting_rays=[rays[j].copy()],
                observation_count=1,
                reprojection_error=0.0,
                model_confidence=conf,
                gps_trajectory_confidence=1.0,
                semantic_class=SemanticClass.UNKNOWN,
                dynamic_probability=0.0,
                visibility=VisibilityState.VISIBLE,
                provenance=Provenance.OBSERVED,
                state=WorldElementState.ACTIVE,
                confidence_score=max(0.3, conf * 0.6),
                confidence_level=ConfidenceLevel.MEDIUM if conf > 0.6 else ConfidenceLevel.LOW,
                last_updated_frame=fid,
            )
            eid = self.store.add_element(elem)
            index.setdefault((gx, gy, gz), []).append(eid)
            new_count += 1

        return fused_count + new_count

    def _fuse_into(
        self,
        elem: WorldElement,
        p: np.ndarray,
        n: np.ndarray,
        c: np.ndarray,
        conf: float,
        ray: np.ndarray,
        fid: int,
    ) -> None:
        """Running weighted update of one surfel from one new cell observation."""
        old_w = float(elem.observation_count) * float(elem.confidence_score)
        new_w = max(1e-6, conf)
        tot = max(1e-6, old_w + new_w)

        elem.position = (old_w * elem.position + new_w * p) / tot
        fused_n = (old_w * elem.normal + new_w * n) / tot
        elem.normal = fused_n / max(1e-9, float(np.linalg.norm(fused_n)))
        elem.color = (old_w * elem.color + new_w * c) / tot

        # Only the first and last ray are ever read, and an unbounded history of every
        # frame that saw a surfel is what makes a long flight run out of memory.
        if len(elem.supporting_rays) < 8:
            elem.supporting_rays.append(ray.copy())
        else:
            elem.supporting_rays[-1] = ray.copy()
        if len(elem.color_observations) < 4:
            elem.color_observations.append((fid, c.copy()))

        elem.supporting_frames.add(fid)
        elem.observation_count += 1
        elem.last_updated_frame = fid
        elem.model_confidence = max(elem.model_confidence, conf)
        elem.confidence_score = min(1.0, elem.confidence_score + 0.15 * conf)
        if len(elem.supporting_frames) >= 2:
            elem.provenance = Provenance.MULTI_VIEW_SUPPORTED
            elem.confidence_level = (
                ConfidenceLevel.HIGH if elem.confidence_score > 0.7 else ConfidenceLevel.MEDIUM
            )
        elem.covariance *= 0.95


    def _voxel_subsample(self, points: np.ndarray, grid_size: float) -> np.ndarray:
        """Fast grid-based spatial subsampling index selector."""
        grid_coords = np.floor(points / grid_size).astype(np.int64)
        # Compute unique voxel hashes
        _, unique_indices = np.unique(grid_coords, axis=0, return_index=True)
        return unique_indices

    def prune_unsupported_hypotheses(self, min_observations: int = 1, min_confidence: float = 0.25) -> int:
        """
        7. Rejects persistent contradictions and noise with insufficient observation support.
        """
        to_remove = []
        for eid, elem in self.store.elements.items():
            if elem.confidence_score < min_confidence or elem.state == WorldElementState.REJECTED:
                to_remove.append(eid)
                
        for eid in to_remove:
            self.store.remove_element(eid)
            
        self.logger.info(f"Pruned {len(to_remove)} unsupported/low-confidence surfels from world store.")
        return len(to_remove)
