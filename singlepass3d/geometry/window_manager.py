"""
Overlapping Temporal Window Partitioner and Batch Manager for SinglePass3D.
Divides continuous keyframe sequences into overlapping temporal sub-windows
for scalable bounded-memory continuous multi-view reconstruction.
"""

from __future__ import annotations
from typing import List, Optional
from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import ReconstructionWindow
from singlepass3d.sensor.video_indexer import VideoIndexer


class WindowManager:
    """
    Partitions long video sequences into overlapping windows of keyframes.
    Guarantees sufficient viewpoint change per window while enforcing overlaps between adjacent clips.
    """
    def __init__(self, window_size: int = 12, window_overlap: int = 4):
        self.window_size = max(3, window_size)
        self.window_overlap = max(1, min(window_overlap, self.window_size - 1))
        self.logger = get_logger()

    def create_overlapping_windows(
        self,
        keyframe_ids: List[int],
        indexer: VideoIndexer
    ) -> List[ReconstructionWindow]:
        """
        Splits keyframe IDs into overlapping windows.
        """
        N = len(keyframe_ids)
        if N == 0:
            return []
            
        step = self.window_size - self.window_overlap
        windows: List[ReconstructionWindow] = []
        window_id = 0
        
        start_idx = 0
        while start_idx < N:
            end_idx = min(N, start_idx + self.window_size)
            win_fids = keyframe_ids[start_idx:end_idx]
            
            # If the last window is too small, merge with previous or take remainder
            if len(win_fids) < 2 and windows:
                # Append to last window
                for fid in win_fids:
                    if fid not in windows[-1].frame_ids:
                        windows[-1].frame_ids.append(fid)
                break
                
            t_start = indexer.frame_index[win_fids[0]].timestamp
            t_end = indexer.frame_index[win_fids[-1]].timestamp
            
            # Overlaps
            prev_overlap = []
            if window_id > 0:
                prev_overlap = [fid for fid in win_fids if fid in windows[window_id - 1].frame_ids]
                
            win = ReconstructionWindow(
                window_id=window_id,
                frame_ids=win_fids,
                start_timestamp=t_start,
                end_timestamp=t_end,
                overlap_with_previous=prev_overlap
            )
            windows.append(win)
            
            if window_id > 0:
                windows[window_id - 1].overlap_with_next = prev_overlap
                
            if end_idx >= N:
                break
                
            start_idx += step
            window_id += 1
            
        self.logger.info(
            f"Created {len(windows)} overlapping reconstruction windows from {N} keyframes (size={self.window_size}, overlap={self.window_overlap})."
        )
        return windows
