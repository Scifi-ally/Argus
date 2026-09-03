"""
Frame Quality Assessment, Blur Detection, Feature Density Analysis,
and Dynamic Motion Estimation for SinglePass3D.
"""

from __future__ import annotations
from typing import Dict, List, Optional
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import FrameMetadata
from singlepass3d.sensor.video_indexer import VideoIndexer


class FrameQualityAnalyzer:
    """
    Evaluates photometric quality, sharpness, blur, feature richness,
    and optical motion for all indexed frames.
    """
    def __init__(self, indexer: VideoIndexer, max_features: int = 2000):
        self.indexer = indexer
        self.max_features = max_features
        self.logger = get_logger()
        self.orb = cv2.ORB_create(nfeatures=self.max_features, fastThreshold=12)

    def analyze_all_frames(self) -> List[FrameMetadata]:
        """
        Processes every frame in indexer and populates quality metrics.
        """
        frame_ids = self.indexer.get_all_frame_ids()
        self.logger.info(f"Analyzing frame quality across {len(frame_ids)} frames...")
        
        prev_gray: Optional[np.ndarray] = None
        
        for fid in frame_ids:
            meta = self.indexer.frame_index[fid]
            img_rgb = self.indexer.get_frame_image(fid, full_resolution=False)
            gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
            hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
            
            # 1. Sharpness (Laplacian variance)
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = float(lap.var())
            
            # 2. Blur score (normalized 0 to 1, where 1 is severely blurred)
            # Low laplacian var -> high blur
            blur = float(1.0 / (1.0 + np.log1p(max(1e-4, sharpness))))
            
            # 3. Exposure balance (0 to 1, ideal ~0.5)
            mean_lum = float(np.mean(gray)) / 255.0
            exposure_score = float(1.0 - abs(mean_lum - 0.5) * 2.0)  # 1.0 is balanced
            
            # 4. Saturation
            saturation = float(np.mean(hsv[:, :, 1])) / 255.0
            
            # 5. Feature count
            kps = self.orb.detect(gray, None)
            feature_count = len(kps)
            
            # 6. Optical flow magnitude & dynamic motion estimate
            flow_mag = 0.0
            dynamic_prob = 0.0
            if prev_gray is not None:
                # Dense Farneback flow on downsampled grid
                small_prev = cv2.resize(prev_gray, (160, 120))
                small_curr = cv2.resize(gray, (160, 120))
                flow = cv2.calcOpticalFlowFarneback(
                    small_prev, small_curr, None, 0.5, 3, 15, 3, 5, 1.2, 0
                )
                mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                flow_mag = float(np.mean(mag))
                
                # Dynamic motion: regions where optical flow deviates substantially from dominant global flow
                median_flow = np.median(flow, axis=(0, 1))
                flow_residual = np.linalg.norm(flow - median_flow, axis=2)
                dynamic_pixels = np.sum(flow_residual > 3.0)
                dynamic_prob = float(dynamic_pixels / max(1, flow_residual.size))
                
            prev_gray = gray
            
            meta.sharpness = sharpness
            meta.blur = blur
            meta.exposure = exposure_score
            meta.saturation = saturation
            meta.feature_count = feature_count
            meta.optical_flow_magnitude = flow_mag
            meta.dynamic_probability = dynamic_prob
            
        self.logger.info(f"Frame quality analysis complete.")
        return [self.indexer.frame_index[fid] for fid in frame_ids]
