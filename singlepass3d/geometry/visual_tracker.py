"""
Visual Feature Tracking, Long 2D-3D Track Maintenance, Lucas-Kanade Optical Flow,
SIFT/ORB Matching, and Outlier Rejection for SinglePass3D.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import Track3D
from singlepass3d.sensor.video_indexer import VideoIndexer


class VisualTracker:
    """
    Builds continuous feature tracks across video sequence using optical flow
    and descriptor matching with forward-backward consistency and epipolar verification.
    """
    def __init__(
        self,
        indexer: VideoIndexer,
        max_features: int = 2000,
        min_track_length: int = 3,
        feature_type: str = "sift"
    ):
        self.indexer = indexer
        self.max_features = max_features
        self.min_track_length = min_track_length
        self.feature_type = feature_type.lower()
        # Anchor re-localisation. Frame-to-frame flow is only ever asked for a small
        # motion, which is what makes it reliable, but chaining hundreds of hops lets
        # the position walk off the feature it started on. Measured on the AGZ pass,
        # against a direct flow from frame 0 gated at 0.7 px forward-backward, the top
        # decile of tracks had drifted 5.4 px by 25 frames, 10.6 px by 50 and 19.5 px
        # by 100. Those observations survive per-track pruning -- a 90-observation
        # track hides a handful of bad ones in its mean -- and bundle adjustment can
        # only down-weight them, so they end up as correlated pose error, which is
        # what sets the depth-agreement floor and therefore the finest voxel the mesh
        # can earn. Each track is instead re-localised from an anchor frame, so error
        # accumulates once per re-anchor rather than once per frame.
        self.anchor_stride = 25
        self.anchor_max_disp_px = 40.0
        self.max_anchor_disagreement_px = 2.0
        # Top the feature set back up as soon as it has lost a tenth of its budget.
        # The old rule waited for half the budget to die, which on a hover never
        # happened: 3000 features were detected on frame 0, 2299 were still alive 350
        # frames later, and not one new feature was detected in between -- so nothing
        # that came into view after the first frame was ever tracked at all.
        self.replenish_fraction = 0.9
        self.logger = get_logger()
        
        if self.feature_type == "sift" and hasattr(cv2, "SIFT_create"):
            self.detector = cv2.SIFT_create(nfeatures=self.max_features)
        else:
            self.detector = cv2.ORB_create(nfeatures=self.max_features)
            
        self.tracks: Dict[int, Track3D] = {}
        self._next_track_id: int = 0

    def track_sequence(self, frame_ids: Optional[List[int]] = None) -> List[Track3D]:
        """
        Runs continuous visual tracking across the selected frame sequence.
        """
        if frame_ids is None:
            frame_ids = self.indexer.get_tracking_frame_ids()
            
        if len(frame_ids) < 2:
            self.logger.warning("Fewer than 2 frames to track.")
            return []
            
        self.logger.info(f"Running visual tracking across {len(frame_ids)} frames...")
        
        # Track state: current active points: track_id -> (u, v)
        active_tracks: Dict[int, np.ndarray] = {}
        prev_gray: Optional[np.ndarray] = None
        anchor_gray: Optional[np.ndarray] = None
        anchor_pts: Dict[int, np.ndarray] = {}
        anchor_age = 0
        lk = dict(winSize=(21, 21), maxLevel=3,
                  criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))
        drift_dropped = 0

        for idx, fid in enumerate(frame_ids):
            img_rgb = self.indexer.get_frame_image(fid, full_resolution=False)
            curr_gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

            # Ensure consistent image resolution across tracking sequence
            if prev_gray is not None and curr_gray.shape != prev_gray.shape:
                curr_gray = cv2.resize(curr_gray, (prev_gray.shape[1], prev_gray.shape[0]))

            if prev_gray is not None and len(active_tracks) > 0:
                track_ids = list(active_tracks.keys())
                pts_prev = np.array([active_tracks[t] for t in track_ids],
                                    dtype=np.float32).reshape(-1, 1, 2)

                # Frame-to-frame flow, forward and backward for cycle consistency.
                pts_curr, st_f, _ = cv2.calcOpticalFlowPyrLK(
                    prev_gray, curr_gray, pts_prev, None, **lk)
                pts_back, st_b, _ = cv2.calcOpticalFlowPyrLK(
                    curr_gray, prev_gray, pts_curr, None, **lk)
                fb = np.linalg.norm(pts_prev - pts_back, axis=2).reshape(-1)
                keep = (st_f[:, 0] == 1) & (st_b[:, 0] == 1) & (fb < 1.5)

                # Re-localise against the anchor frame, seeded with the chained guess
                # so the search starts close even when the anchor is 25 frames old.
                # The anchor position carries no accumulated drift, so where the two
                # agree it wins; where they disagree by more than a couple of pixels
                # the track has walked off its feature and is dropped rather than
                # carried at a plausible-looking wrong pixel.
                if anchor_gray is not None:
                    pts_anch = np.array([anchor_pts.get(t, active_tracks[t]) for t in track_ids],
                                        dtype=np.float32).reshape(-1, 1, 2)
                    seed = pts_curr.copy()
                    a_fwd, a_sf, _ = cv2.calcOpticalFlowPyrLK(
                        anchor_gray, curr_gray, pts_anch, seed,
                        flags=cv2.OPTFLOW_USE_INITIAL_FLOW, **lk)
                    a_bwd, a_sb, _ = cv2.calcOpticalFlowPyrLK(
                        curr_gray, anchor_gray, a_fwd, None, **lk)
                    a_fb = np.linalg.norm(pts_anch - a_bwd, axis=2).reshape(-1)
                    a_ok = (a_sf[:, 0] == 1) & (a_sb[:, 0] == 1) & (a_fb < 1.0)
                    gap = np.linalg.norm(a_fwd - pts_curr, axis=2).reshape(-1)
                    trust = a_ok & (gap <= self.max_anchor_disagreement_px)
                    pts_curr = np.where(trust.reshape(-1, 1, 1), a_fwd, pts_curr)
                    drift_dropped += int((keep & ~trust).sum())
                    keep &= trust

                new_active: Dict[int, np.ndarray] = {}
                h, w = curr_gray.shape
                for i, tid in enumerate(track_ids):
                    if not keep[i]:
                        continue
                    u, v = pts_curr[i, 0]
                    if 0 <= u < w and 0 <= v < h:
                        new_active[tid] = np.array([u, v], dtype=np.float64)
                        self.tracks[tid].observations[fid] = np.array([u, v], dtype=np.float64)

                active_tracks = new_active
                anchor_pts = {t: q for t, q in anchor_pts.items() if t in active_tracks}

            # Replenish as soon as a tenth of the budget has died, and always on the
            # first frame. Detection is masked around live tracks, so what gets added
            # is surface that nothing is currently following.
            replenished = False
            if len(active_tracks) < int(self.max_features * self.replenish_fraction) or idx == 0:
                mask = np.full(curr_gray.shape, 255, dtype=np.uint8)
                for pt in active_tracks.values():
                    u, v = int(round(pt[0])), int(round(pt[1]))
                    cv2.circle(mask, (u, v), 8, 0, -1)

                needed = self.max_features - len(active_tracks)
                new_kps = []
                try:
                    detected = self.detector.detect(curr_gray, mask=mask)
                    new_kps = list(detected) if detected is not None else []
                except Exception:
                    new_kps = []

                # If SIFT/ORB found few keypoints, supplement with goodFeaturesToTrack (Shi-Tomasi)
                if len(new_kps) < 50:
                    gftt_pts = cv2.goodFeaturesToTrack(
                        curr_gray, maxCorners=needed, qualityLevel=0.01, minDistance=10, mask=mask
                    )
                    if gftt_pts is not None:
                        for p_arr in gftt_pts:
                            px, py = p_arr[0]
                            kp = cv2.KeyPoint(x=float(px), y=float(py), size=10.0, response=1.0)
                            new_kps.append(kp)

                new_kps = sorted(new_kps, key=lambda k: k.response, reverse=True)[:needed]
                for kp in new_kps:
                    tid = self._next_track_id
                    self._next_track_id += 1
                    u, v = float(kp.pt[0]), float(kp.pt[1])
                    track = Track3D(track_id=tid)
                    track.observations[fid] = np.array([u, v], dtype=np.float64)
                    self.tracks[tid] = track
                    active_tracks[tid] = np.array([u, v], dtype=np.float64)
                replenished = bool(new_kps)

            # Re-key. Newly born tracks only have a position in this frame, so a
            # replenish always becomes the new anchor; otherwise re-anchor once the
            # anchor is stale or the view has moved far enough from it that its
            # appearance no longer matches.
            anchor_age += 1
            stale = anchor_age >= self.anchor_stride
            if active_tracks and anchor_gray is not None and not stale and anchor_pts:
                shared = [t for t in active_tracks if t in anchor_pts]
                if shared:
                    disp = np.linalg.norm(
                        np.array([active_tracks[t] for t in shared])
                        - np.array([anchor_pts[t] for t in shared]), axis=1)
                    stale = bool(np.median(disp) > self.anchor_max_disp_px)
            if active_tracks and (anchor_gray is None or replenished or stale):
                anchor_gray = curr_gray
                anchor_pts = {t: q.copy() for t, q in active_tracks.items()}
                anchor_age = 0

            prev_gray = curr_gray
            
        # Filter out short tracks
        valid_tracks = [t for t in self.tracks.values() if len(t.observations) >= self.min_track_length]
        obs = sum(len(t.observations) for t in valid_tracks)
        self.logger.info(
            f"Visual tracking generated {len(self.tracks)} total tracks, "
            f"{len(valid_tracks)} valid long tracks (>= {self.min_track_length} frames), "
            f"{obs} observations; {drift_dropped} dropped for disagreeing with their anchor frame."
        )
        return valid_tracks

    def get_frame_pair_matches(self, frame_id_1: int, frame_id_2: int) -> Tuple[np.ndarray, np.ndarray, List[int]]:
        """
        Finds common 2D point correspondences between two frames from tracked features.
        Returns:
            pts1: (N, 2)
            pts2: (N, 2)
            track_ids: List of track IDs
        """
        pts1_list: List[np.ndarray] = []
        pts2_list: List[np.ndarray] = []
        track_ids: List[int] = []
        
        for tid, track in self.tracks.items():
            if frame_id_1 in track.observations and frame_id_2 in track.observations:
                pts1_list.append(track.observations[frame_id_1])
                pts2_list.append(track.observations[frame_id_2])
                track_ids.append(tid)
                
        if not pts1_list:
            return np.empty((0, 2)), np.empty((0, 2)), []
            
        return np.array(pts1_list), np.array(pts2_list), track_ids
