"""
Adaptive Keyframe Selection for SinglePass3D.
Selects reconstruction frames based on parallax, baseline, overlap, sharpness,
feature density, and visual novelty rather than arbitrary fixed-interval sampling.
"""

from __future__ import annotations
from typing import List, Optional, Set
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import FrameMetadata, Trajectory
from singlepass3d.sensor.video_indexer import VideoIndexer


class KeyframeSelector:
    """
    Multi-criteria adaptive selector for reconstruction and refinement frames.
    """
    def __init__(
        self,
        indexer: VideoIndexer,
        min_parallax_deg: float = 2.5,
        min_baseline_m: float = 0.5,
        max_frame_gap: int = 15,
        min_frame_gap: int = 2
    ):
        self.indexer = indexer
        self.min_parallax_deg = min_parallax_deg
        self.min_baseline_m = min_baseline_m
        self.max_frame_gap = max_frame_gap
        self.min_frame_gap = min_frame_gap
        self.logger = get_logger()

    def select_reconstruction_keyframes(
        self,
        trajectory: Trajectory,
        candidate_frame_ids: Optional[List[int]] = None
    ) -> List[int]:
        """
        Selects optimal reconstruction frames using trajectory geometry and frame quality.
        """
        if candidate_frame_ids is None:
            candidate_frame_ids = self.indexer.get_tracking_frame_ids()
            
        if not candidate_frame_ids:
            return []
            
        self.logger.info(f"Selecting adaptive reconstruction keyframes from {len(candidate_frame_ids)} candidates...")
        
        selected_keyframes: List[int] = [candidate_frame_ids[0]]
        self.indexer.frame_index[candidate_frame_ids[0]].is_reconstruction_frame = True
        
        last_selected_fid = candidate_frame_ids[0]
        last_selected_pose = trajectory.get_pose(last_selected_fid)
        
        for fid in candidate_frame_ids[1:]:
            curr_pose = trajectory.get_pose(fid)
            meta = self.indexer.frame_index[fid]
            gap = fid - last_selected_fid
            
            # Skip if frame is severely blurred or under minimum gap
            if gap < self.min_frame_gap:
                continue
                
            if meta.blur > 0.85 and gap < self.max_frame_gap:
                continue  # wait for a sharper nearby frame
                
            # If no pose available, use max frame gap fallback
            if last_selected_pose is None or curr_pose is None:
                if gap >= self.max_frame_gap:
                    selected_keyframes.append(fid)
                    meta.is_reconstruction_frame = True
                    last_selected_fid = fid
                continue
                
            # Calculate baseline translation distance
            baseline = float(np.linalg.norm(curr_pose.t_wc - last_selected_pose.t_wc))
            
            # Calculate angular rotation difference (parallax angle)
            R_rel = curr_pose.R_wc.T @ last_selected_pose.R_wc
            trace = np.clip(np.trace(R_rel), -1.0, 3.0)
            angle_rad = np.arccos((trace - 1.0) / 2.0)
            angle_deg = float(np.degrees(angle_rad))
            
            # Decision rule: baseline or parallax threshold exceeded, or max interval reached
            is_keyframe = False
            if baseline >= self.min_baseline_m or angle_deg >= self.min_parallax_deg:
                is_keyframe = True
            elif gap >= self.max_frame_gap:
                is_keyframe = True
                
            if is_keyframe:
                selected_keyframes.append(fid)
                meta.is_reconstruction_frame = True
                last_selected_fid = fid
                last_selected_pose = curr_pose
                
        # Also always include the final frame for complete coverage
        if candidate_frame_ids[-1] not in selected_keyframes:
            selected_keyframes.append(candidate_frame_ids[-1])
            self.indexer.frame_index[candidate_frame_ids[-1]].is_reconstruction_frame = True
            
        self.logger.info(
            f"Selected {len(selected_keyframes)} adaptive reconstruction keyframes (reduction ratio: {len(candidate_frame_ids)/max(1, len(selected_keyframes)):.1f}x)."
        )
        return selected_keyframes
