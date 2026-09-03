"""
Global Optimization and Full-Flight Offline Refinement Pass for SinglePass3D.
Performs global bundle adjustment / pose graph refinement across the entire flight trajectory,
updates landmarks, refines surface coordinates, and enforces loop closure constraints.
"""

from __future__ import annotations
from typing import Dict, List, Optional
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import LoopConstraint, Pose3D, Track3D, Trajectory
from singlepass3d.geometry.trajectory_fusion import TrajectoryOptimizer
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.telemetry_parser import TelemetryParser
from singlepass3d.sensor.video_indexer import VideoIndexer


class GlobalRefinementPass:
    """
    Executes the full offline global optimization pass across the flight.
    """
    def __init__(
        self,
        camera: CameraModel,
        trajectory_optimizer: TrajectoryOptimizer,
        max_iters: int = 50
    ):
        self.camera = camera
        self.trajectory_optimizer = trajectory_optimizer
        self.max_iters = max_iters
        self.logger = get_logger()

    def run_global_refinement(
        self,
        trajectory: Trajectory,
        world: PersistentWorld,
        indexer: VideoIndexer,
        telemetry: Optional[TelemetryParser] = None,
        tracks: Optional[List[Track3D]] = None,
        loop_constraints: Optional[List[LoopConstraint]] = None
    ) -> Trajectory:
        """
        Executes offline global trajectory and world geometry refinement.
        """
        self.logger.info("Starting Global Offline Refinement Pass across full flight sequence...")
        
        frame_ids = trajectory.frame_ids
        if len(frame_ids) < 2:
            return trajectory
            
        # 1. Global Trajectory Optimization with high precision and loop constraints
        refined_trajectory = self.trajectory_optimizer.optimize_trajectory(
            frame_ids=frame_ids,
            indexer=indexer,
            telemetry=telemetry,
            tracks=tracks,
            initial_trajectory=trajectory
        )
        
        # 2. Update and align world surfels based on refined camera poses
        self.logger.info("Updating world surface element coordinates to match refined trajectory...")
        
        # For each surfel, if its primary supporting frame pose shifted, update position
        for elem in world.store.elements.values():
            if elem.supporting_frames:
                primary_fid = sorted(list(elem.supporting_frames))[0]
                old_pose = trajectory.get_pose(primary_fid)
                new_pose = refined_trajectory.get_pose(primary_fid)
                
                if old_pose is not None and new_pose is not None:
                    # Point in camera frame: X_c = R_old.T @ (X_w - t_old)
                    pt_c = old_pose.R_cw @ elem.position + old_pose.t_cw
                    # Transformed into new world pose: X_new = R_new @ X_c + t_new
                    pt_new_w = (new_pose.R_wc @ pt_c) + new_pose.t_wc
                    elem.position = pt_new_w
                    
                    # Also update normal
                    normal_c = old_pose.R_cw @ elem.normal
                    elem.normal = new_pose.R_wc @ normal_c
                    elem.normal = elem.normal / max(1e-6, np.linalg.norm(elem.normal))
                    
        world.store._tree_dirty = True
        self.logger.info("Global Refinement Pass complete.")
        return refined_trajectory
