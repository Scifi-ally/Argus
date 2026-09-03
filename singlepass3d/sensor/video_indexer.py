"""
Video Ingestion and Multi-tier Frame Indexing for SinglePass3D.
Preserves original resolution frames while generating efficient proxy frames for fast tracking.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import FrameMetadata


class VideoIndexer:
    """
    Decodes full video sequence, extracts timestamps, builds the indexed frame store,
    and manages tiered low-resolution proxy and full-resolution frame caches.
    """
    def __init__(self, video_path: str | Path, work_dir: str | Path, proxy_max_dim: int = 960, tracking_step: int = 1):
        self.video_path = Path(video_path)
        self.work_dir = Path(work_dir)
        self.proxy_max_dim = proxy_max_dim
        self.tracking_step = max(1, tracking_step)
        self.logger = get_logger()
        
        self.frames_dir = self.work_dir / "frames"
        self.proxy_dir = self.frames_dir / "proxy"
        self.fullres_dir = self.frames_dir / "fullres"
        self.proxy_dir.mkdir(parents=True, exist_ok=True)
        self.fullres_dir.mkdir(parents=True, exist_ok=True)
        
        self.frame_index: Dict[int, FrameMetadata] = {}
        self.fps: float = 30.0
        self.total_frames: int = 0
        self.duration_seconds: float = 0.0
        self.original_width: int = 0
        self.original_height: int = 0

        # Lens rectification state. When a source camera model is installed every
        # frame handed out by get_frame_image() is an ideal pinhole image, so
        # tracking, SfM and stereo all operate on straight epipolar geometry.
        self._undistort_camera = None
        self._undistort_target = None
        self._undistort_maps: Dict[Tuple[int, int], Tuple[np.ndarray, np.ndarray]] = {}

    def index_video(self, max_frames: Optional[int] = None) -> List[FrameMetadata]:
        """
        Scans video or image directory, generates proxy frames for tracking, indexes metadata.
        """
        if not self.video_path.exists():
            raise FileNotFoundError(f"Video path not found: {self.video_path}")
            
        indexed_list: List[FrameMetadata] = []
        
        # Check if input is a directory of images
        if self.video_path.is_dir():
            image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
            image_files = sorted([
                f for f in self.video_path.iterdir()
                if f.suffix.lower() in image_extensions
            ])
            
            if not image_files:
                raise ValueError(f"No image files found in directory: {self.video_path}")
                
            self.total_frames = len(image_files) if not max_frames else min(len(image_files), max_frames)
            
            # Read first image to obtain resolution
            first_img = cv2.imread(str(image_files[0]))
            if first_img is None:
                raise RuntimeError(f"Failed to read image: {image_files[0]}")
                
            self.original_height, self.original_width = first_img.shape[:2]
            self.duration_seconds = self.total_frames / self.fps
            
            self.logger.info(
                f"Indexing image sequence folder: {self.video_path.name} ({self.original_width}x{self.original_height}, {self.total_frames} frames)"
            )
            
            max_dim = max(self.original_width, self.original_height)
            scale = min(1.0, float(self.proxy_max_dim) / max(1, max_dim))
            proxy_w = int(round(self.original_width * scale))
            proxy_h = int(round(self.original_height * scale))
            
            for frame_id in range(self.total_frames):
                img_p = image_files[frame_id]
                timestamp = frame_id / self.fps
                
                proxy_path = self.proxy_dir / f"frame_{frame_id:06d}_proxy.jpg"
                if not proxy_path.exists():
                    frame = cv2.imread(str(img_p))
                    if scale < 1.0 and frame is not None:
                        proxy_frame = cv2.resize(frame, (proxy_w, proxy_h), interpolation=cv2.INTER_AREA)
                    else:
                        proxy_frame = frame
                    if proxy_frame is not None:
                        cv2.imwrite(str(proxy_path), proxy_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                        
                is_tracking = (frame_id % self.tracking_step == 0)
                meta = FrameMetadata(
                    frame_id=frame_id,
                    timestamp=timestamp,
                    original_index=frame_id,
                    width=self.original_width,
                    height=self.original_height,
                    proxy_path=str(proxy_path),
                    fullres_path=str(img_p),
                    is_tracking_frame=is_tracking,
                    is_reconstruction_frame=False,
                    is_refinement_frame=False
                )
                self.frame_index[frame_id] = meta
                indexed_list.append(meta)
                
            self.logger.info(f"Image folder indexing complete: {self.total_frames} frames indexed.")
            return indexed_list

        # Otherwise read as video file
        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video file: {self.video_path}")
            
        self.original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        reported_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        self.logger.info(
            f"Indexing video: {self.video_path.name} ({self.original_width}x{self.original_height} @ {self.fps:.2f} fps, ~{reported_count} frames)"
        )
        
        frame_id = 0
        raw_idx = 0
        
        # Calculate scale factor for proxy
        max_dim = max(self.original_width, self.original_height)
        scale = min(1.0, float(self.proxy_max_dim) / max(1, max_dim))
        proxy_w = int(round(self.original_width * scale))
        proxy_h = int(round(self.original_height * scale))
        
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
                
            if max_frames and frame_id >= max_frames:
                break
                
            # Timestamp calculation
            pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            timestamp = pos_msec / 1000.0 if pos_msec > 0 else raw_idx / self.fps
            
            # Save proxy frame
            proxy_filename = f"frame_{frame_id:06d}_proxy.jpg"
            proxy_path = self.proxy_dir / proxy_filename
            
            if scale < 1.0:
                proxy_frame = cv2.resize(frame, (proxy_w, proxy_h), interpolation=cv2.INTER_AREA)
            else:
                proxy_frame = frame
                
            if not proxy_path.exists():
                cv2.imwrite(str(proxy_path), proxy_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                
            # Save full-res on demand or if small
            fullres_path = self.fullres_dir / f"frame_{frame_id:06d}_full.jpg"
            
            is_tracking = (raw_idx % self.tracking_step == 0)
            
            meta = FrameMetadata(
                frame_id=frame_id,
                timestamp=timestamp,
                original_index=raw_idx,
                width=self.original_width,
                height=self.original_height,
                proxy_path=str(proxy_path),
                fullres_path=str(fullres_path),
                is_tracking_frame=is_tracking,
                is_reconstruction_frame=False,
                is_refinement_frame=False
            )
            
            self.frame_index[frame_id] = meta
            indexed_list.append(meta)
            
            frame_id += 1
            raw_idx += 1
            
        cap.release()
        self.total_frames = frame_id
        self.duration_seconds = frame_id / self.fps if self.fps > 0 else 0.0
        
        self.logger.info(f"Video indexing complete: {self.total_frames} frames indexed across {self.duration_seconds:.2f}s")
        return indexed_list

    def set_undistortion(self, camera, target=None) -> None:
        """
        Installs lens rectification. `camera` is the distorted (as-calibrated) model;
        every returned frame is then remapped into `target`'s ideal pinhole geometry.
        """
        if camera is None or np.allclose(camera.data.distortion, 0):
            self._undistort_camera = None
            self._undistort_target = None
            self._undistort_maps.clear()
            return
        self._undistort_camera = camera
        self._undistort_target = target or camera.undistorted_model()
        self._undistort_maps.clear()
        self.logger.info("Lens rectification enabled for all indexed frames.")

    @property
    def undistortion_enabled(self) -> bool:
        return self._undistort_camera is not None

    def rectified_camera(self):
        """The ideal pinhole model matching the frames this indexer returns."""
        return self._undistort_target

    def _rectify(self, img: np.ndarray) -> np.ndarray:
        if self._undistort_camera is None or img is None:
            return img
        h, w = img.shape[:2]
        maps = self._undistort_maps.get((w, h))
        if maps is None:
            maps = self._undistort_camera.undistort_maps(w, h, self._undistort_target)
            self._undistort_maps[(w, h)] = maps
        return cv2.remap(img, maps[0], maps[1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def get_frame_image(self, frame_id: int, full_resolution: bool = False) -> np.ndarray:
        """
        Loads the image for frame_id. Returns RGB uint8 numpy array (H, W, 3).
        """
        meta = self.frame_index.get(frame_id)
        if meta is None:
            raise KeyError(f"Frame ID {frame_id} not in video index.")
            
        if full_resolution:
            # Check if cached full-res exists
            full_path = Path(meta.fullres_path) if meta.fullres_path else None
            if full_path and full_path.exists():
                bgr = cv2.imread(str(full_path))
                if bgr is not None:
                    return cv2.cvtColor(self._rectify(bgr), cv2.COLOR_BGR2RGB)
                    
            # Otherwise extract from video directly
            cap = cv2.VideoCapture(str(self.video_path))
            cap.set(cv2.CAP_PROP_POS_FRAMES, meta.original_index)
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                # Save to fullres cache for repeated fast access
                if full_path:
                    cv2.imwrite(str(full_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
                return cv2.cvtColor(self._rectify(frame), cv2.COLOR_BGR2RGB)
            else:
                # Fallback to proxy
                self.logger.warning(f"Could not seek full-res frame {frame_id}, falling back to proxy.")
                
        # Return proxy frame
        proxy_path = Path(meta.proxy_path) if meta.proxy_path else None
        if proxy_path and proxy_path.exists():
            bgr = cv2.imread(str(proxy_path))
            if bgr is not None:
                return cv2.cvtColor(self._rectify(bgr), cv2.COLOR_BGR2RGB)
                
        raise RuntimeError(f"Could not load image for frame {frame_id}")

    def get_all_frame_ids(self) -> List[int]:
        return sorted(list(self.frame_index.keys()))

    def get_tracking_frame_ids(self) -> List[int]:
        return [fid for fid, meta in sorted(self.frame_index.items()) if meta.is_tracking_frame]
