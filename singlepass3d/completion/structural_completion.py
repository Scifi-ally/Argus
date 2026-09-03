"""
Geometry-Supported Structural Completion and Architectural Planar Regularization for SinglePass3D.
Performs plane detection, vertical gravity alignment, and constrained small-gap interpolation
while strictly tagging all resulting elements as STRUCTURAL_INFERRED.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from scipy.spatial import cKDTree
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import (
    ConfidenceLevel,
    Provenance,
    SemanticClass,
    VisibilityState,
    WorldElement,
    WorldElementState,
)
from singlepass3d.metric_world.persistent_world import PersistentWorld


def fit_plane_ransac(
    points: np.ndarray,
    distance_threshold: float = 0.08,
    max_iters: int = 150
) -> Tuple[Optional[np.ndarray], Optional[float], np.ndarray]:
    """
    RANSAC plane fitting: finds normal n (unit) and d such that n . p + d = 0.
    Returns: (normal (3,), d float, inliers_mask (N,) bool)
    """
    N = len(points)
    if N < 10:
        return None, None, np.zeros(N, dtype=bool)
        
    best_inliers = np.zeros(N, dtype=bool)
    best_normal = None
    best_d = None
    max_inlier_count = 0
    
    for _ in range(max_iters):
        sample_idx = np.random.choice(N, 3, replace=False)
        p1, p2, p3 = points[sample_idx]
        
        # Plane normal via cross product
        v1 = p2 - p1
        v2 = p3 - p1
        n = np.cross(v1, v2)
        norm = np.linalg.norm(n)
        if norm < 1e-6:
            continue
        n = n / norm
        d = -float(np.dot(n, p1))
        
        # Distance of all points to plane: |n . p + d|
        dists = np.abs(np.dot(points, n) + d)
        inliers = dists < distance_threshold
        count = int(np.sum(inliers))
        
        if count > max_inlier_count:
            max_inlier_count = count
            best_inliers = inliers
            best_normal = n
            best_d = d
            
    return best_normal, best_d, best_inliers


class StructuralCompleter:
    """
    Applies geometry-grounded architectural plane continuation and small-gap completion.
    """
    def __init__(
        self,
        plane_dist_thresh_m: float = 0.06,
        min_plane_inliers: int = 40,
        max_gap_size_m: float = 1.2
    ):
        self.plane_dist_thresh_m = plane_dist_thresh_m
        self.min_plane_inliers = min_plane_inliers
        self.max_gap_size_m = max_gap_size_m
        self.logger = get_logger()

    def apply_structural_completion(self, world: PersistentWorld) -> int:
        """
        Detects planar facades and roofs, regularizes their geometry,
        and interpolates small internal unsupported gaps.
        """
        self.logger.info("Running Geometry-Supported Structural Completion on architectural regions...")
        
        # Extract facade and roof elements
        arch_eids: List[int] = []
        arch_pts: List[np.ndarray] = []
        
        for eid, elem in world.store.elements.items():
            if elem.semantic_class in [SemanticClass.FACADE, SemanticClass.ROOF, SemanticClass.BUILDING]:
                arch_eids.append(eid)
                arch_pts.append(elem.position)
                
        if len(arch_pts) < self.min_plane_inliers:
            self.logger.info("Insufficient architectural points for planar structural completion.")
            return 0
            
        pts_arr = np.array(arch_pts, dtype=np.float64)
        
        # Fit dominant architectural plane
        normal, d, inliers = fit_plane_ransac(
            pts_arr,
            distance_threshold=self.plane_dist_thresh_m,
            max_iters=200
        )
        
        if normal is None or np.sum(inliers) < self.min_plane_inliers:
            self.logger.info("No dominant planar structure detected.")
            return 0
            
        inlier_eids = [arch_eids[i] for i in range(len(arch_eids)) if inliers[i]]
        inlier_pts = pts_arr[inliers]
        
        # 1. Planar Regularization: Project noisy observed surfels slightly onto the best-fit plane
        # For facades, enforce vertical wall alignment (gravity normal n_z = 0)
        is_facade = abs(normal[2]) < 0.4
        if is_facade:
            normal[2] = 0.0
            normal = normal / max(1e-6, np.linalg.norm(normal))
            # recompute d with centroid
            centroid = np.mean(inlier_pts, axis=0)
            d = -float(np.dot(normal, centroid))
            
        for eid in inlier_eids:
            elem = world.store.elements[eid]
            # Snap normal
            elem.normal = normal.copy()
            # Slight projection onto plane
            dist_to_plane = float(np.dot(normal, elem.position) + d)
            elem.position = elem.position - normal * (dist_to_plane * 0.5)
            
        # 2. Small Hole Interpolation: Find bounds and add intermediate surfels
        # Project inlier points to 2D plane coordinate system (u_axis, v_axis)
        u_axis = np.array([normal[1], -normal[0], 0.0], dtype=np.float64)
        if np.linalg.norm(u_axis) < 1e-4:
            u_axis = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        u_axis = u_axis / np.linalg.norm(u_axis)
        v_axis = np.cross(normal, u_axis)

        inlier_uv = np.column_stack([
            np.dot(inlier_pts, u_axis),
            np.dot(inlier_pts, v_axis)
        ])

        u_min, u_max = np.min(inlier_uv[:, 0]), np.max(inlier_uv[:, 0])
        v_min, v_max = np.min(inlier_uv[:, 1]), np.max(inlier_uv[:, 1])

        # Sample regular grid across plane bounding box
        grid_step = world.voxel_size_m * 1.5
        u_samples = np.arange(u_min, u_max, grid_step)
        v_samples = np.arange(v_min, v_max, grid_step)

        ref_color = np.mean([world.store.elements[eid].color for eid in inlier_eids[:20]], axis=0)

        # Every candidate cell on the plane, tested against the world in one batch.
        #
        # Asking the store for the nearest element one cell at a time was three and a
        # half minutes of every run. Two reasons, and inserting a surfel triggers both:
        # the voxel-hash path walks a 7x7x7 neighbourhood in Python for each cell, and
        # when a cell sits in a void -- which is every cell worth filling -- it falls
        # through to the KD-tree, which `add_element` has just marked dirty, so the
        # tree is rebuilt over the whole store. Five hundred insertions, five hundred
        # rebuilds of a four-hundred-thousand-element tree. Building the tree once and
        # querying the whole grid against it answers the same question, with the same
        # distance window, in a couple of seconds.
        uu, vv = np.meshgrid(u_samples, v_samples, indexing="ij")
        cand = (
            uu.reshape(-1, 1) * u_axis.reshape(1, 3)
            + vv.reshape(-1, 1) * v_axis.reshape(1, 3)
            - d * normal.reshape(1, 3)
        )
        if cand.shape[0] == 0:
            self.logger.info("No candidate structural gap cells on the detected plane.")
            return 0

        active = [
            e.position for e in world.store.elements.values()
            if e.state != WorldElementState.REJECTED
        ]
        if not active:
            return 0
        tree = cKDTree(np.asarray(active, dtype=np.float64))
        dist, _ = tree.query(cand, k=1, workers=-1)

        # Same window as before: far enough out to be a real gap, close enough in to be
        # interpolation between observations rather than an invented extension.
        fill = np.flatnonzero((dist > 0.08) & (dist <= self.max_gap_size_m))
        # The grid is generated column-major above, matching the original nested loop
        # order, so the 500 cap keeps taking the same cells it always did.
        fill = fill[:500]

        added_structural_count = 0
        for k in fill:
            p_3d = cand[k]
            inferred_elem = WorldElement(
                element_id=-1,
                position=p_3d,
                normal=normal.copy(),
                covariance=np.eye(3, dtype=np.float64) * 0.02,
                color=ref_color.copy(),
                color_observations=[],
                supporting_frames=set(),
                supporting_rays=[],
                observation_count=1,
                reprojection_error=1.5,
                model_confidence=0.6,
                gps_trajectory_confidence=1.0,
                semantic_class=SemanticClass.FACADE if is_facade else SemanticClass.ROOF,
                dynamic_probability=0.0,
                visibility=VisibilityState.VISIBLE,
                provenance=Provenance.STRUCTURAL_INFERRED,
                state=WorldElementState.ACTIVE,
                confidence_score=0.65,
                confidence_level=ConfidenceLevel.MEDIUM
            )
            world.store.add_element(inferred_elem)
            added_structural_count += 1

        world.store._tree_dirty = True
        self.logger.info(
            f"Structural completion added {added_structural_count} STRUCTURAL_INFERRED elements across architectural gaps."
        )
        return added_structural_count
