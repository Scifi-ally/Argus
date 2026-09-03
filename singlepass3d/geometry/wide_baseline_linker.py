"""
Wide-baseline linking across the whole pass.

Frame-to-frame flow gives excellent local geometry and no long-range geometry at
all: a track that dies after forty frames never tells bundle adjustment how frame
0 relates to frame 150. On a hovering or orbiting pass those two frames can be
metres apart while looking at the same wall, and that pair is exactly what dense
stereo triangulates against -- so its relative pose is the number that sets depth
precision, and nothing in a purely sequential track set constrains it.

Measured on the AGZ pass before this stage existed: neighbouring keyframes agreed
to 0.42 px of epipolar error while pairs 2.5 m apart -- the ones the plane sweep
actually uses as source views -- were off by 2.39 px, against 0.55 px for an
essential matrix fitted to the same correspondences. That gap is unconstrained
pose error, and at 10 m range with a 2.5 m baseline every pixel of it is 8.6 cm of
depth uncertainty, which is why most photometrically matched pixels failed
cross-view corroboration and were discarded as holes.

This stage detects features on a spread of anchor frames, matches every anchor
pair directly, and merges the surviving correspondences into multi-frame tracks.
Those tracks are handed to the same bundle adjustment as the flow tracks, where
they act as loop closures over the entire flight.
"""

from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from ..core.types import Track3D
from singlepass3d.core.logging import get_logger


class WideBaselineLinker:
    """Builds long-range feature tracks by matching anchor frames to each other."""

    def __init__(
        self,
        indexer,
        camera,
        anchor_stride: int = 8,
        max_anchors: int = 48,
        max_features: int = 3000,
        ratio: float = 0.8,
        min_inliers: int = 30,
        ransac_px: float = 1.5,
        min_track_frames: int = 3,
    ):
        self.indexer = indexer
        self.camera = camera
        self.anchor_stride = int(max(1, anchor_stride))
        self.max_anchors = int(max(3, max_anchors))
        self.max_features = int(max_features)
        self.ratio = float(ratio)
        self.min_inliers = int(min_inliers)
        self.ransac_px = float(ransac_px)
        self.min_track_frames = int(max(2, min_track_frames))
        self.logger = get_logger()
        self.stats: Dict[str, float] = {}
        self._sift = cv2.SIFT_create(nfeatures=self.max_features)
        self._flann = cv2.FlannBasedMatcher(dict(algorithm=1, trees=4), dict(checks=32))

    def _anchors(self, frame_ids: Sequence[int]) -> List[int]:
        fids = sorted(int(f) for f in frame_ids)
        if len(fids) <= self.max_anchors:
            return fids
        picked = fids[:: self.anchor_stride]
        if len(picked) > self.max_anchors:
            idx = np.linspace(0, len(fids) - 1, self.max_anchors).round().astype(int)
            picked = [fids[i] for i in sorted(set(idx.tolist()))]
        return picked

    def _features(self, fid: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        img = self.indexer.get_frame_image(fid, full_resolution=False)
        if img is None:
            return None, None
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        kp, desc = self._sift.detectAndCompute(gray, None)
        if desc is None or len(kp) < 8:
            return None, None
        pts = np.array([k.pt for k in kp], dtype=np.float32)
        return pts, desc.astype(np.float32)

    def _match_pair(self, da: np.ndarray, db: np.ndarray,
                    pa: np.ndarray, pb: np.ndarray,
                    K: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Ratio-tested matches that also survive a two-view geometry check."""
        raw = self._flann.knnMatch(da, db, k=2)
        ia: List[int] = []
        ib: List[int] = []
        for m in raw:
            if len(m) == 2 and m[0].distance < self.ratio * m[1].distance:
                ia.append(m[0].queryIdx)
                ib.append(m[0].trainIdx)
        if len(ia) < self.min_inliers:
            return None
        ia_arr = np.asarray(ia, dtype=np.int32)
        ib_arr = np.asarray(ib, dtype=np.int32)
        # A ratio test alone keeps repeated-texture matches, and a facade is mostly
        # repeated texture; the essential matrix is what removes them.
        E, mask = cv2.findEssentialMat(
            pa[ia_arr], pb[ib_arr], K, cv2.USAC_MAGSAC, 0.999, self.ransac_px
        )
        if E is None or mask is None:
            return None
        keep = mask.ravel().astype(bool)
        if int(keep.sum()) < self.min_inliers:
            return None
        return ia_arr[keep], ib_arr[keep]

    @staticmethod
    def _find(parent: Dict[int, int], x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def link(self, frame_ids: Sequence[int], track_id_offset: int = 1_000_000) -> List[Track3D]:
        """Long-range tracks over the anchor frames, ready for bundle adjustment."""
        anchors = self._anchors(frame_ids)
        if len(anchors) < 3:
            return []
        K = np.asarray(self.camera.K, dtype=np.float64)

        pts: List[Optional[np.ndarray]] = []
        desc: List[Optional[np.ndarray]] = []
        for fid in anchors:
            p, d = self._features(fid)
            pts.append(p)
            desc.append(d)
        usable = [i for i in range(len(anchors)) if desc[i] is not None]
        if len(usable) < 3:
            return []

        stride = max(1, max((len(p) for p in pts if p is not None), default=1) + 1)
        parent: Dict[int, int] = {}

        def node(ai: int, ki: int) -> int:
            n = ai * stride + ki
            if n not in parent:
                parent[n] = n
            return n

        tried = 0
        accepted = 0
        inliers_total = 0
        for oi, i in enumerate(usable):
            for j in usable[oi + 1:]:
                tried += 1
                m = self._match_pair(desc[i], desc[j], pts[i], pts[j], K)
                if m is None:
                    continue
                accepted += 1
                inliers_total += len(m[0])
                for ka, kb in zip(m[0].tolist(), m[1].tolist()):
                    ra = self._find(parent, node(i, ka))
                    rb = self._find(parent, node(j, kb))
                    if ra != rb:
                        parent[ra] = rb

        groups: Dict[int, List[int]] = {}
        for n in parent:
            groups.setdefault(self._find(parent, n), []).append(n)

        tracks: List[Track3D] = []
        contradictory = 0
        for members in groups.values():
            if len(members) < self.min_track_frames:
                continue
            obs: Dict[int, np.ndarray] = {}
            bad = False
            for n in members:
                ai, ki = divmod(n, stride)
                fid = anchors[ai]
                if fid in obs:
                    # Two features in one frame cannot be the same world point; the
                    # chain that merged them went through a mismatch, so drop it
                    # rather than feed bundle adjustment a contradiction.
                    bad = True
                    break
                obs[fid] = np.asarray(pts[ai][ki], dtype=np.float64).reshape(2)
            if bad:
                contradictory += 1
                continue
            if len(obs) < self.min_track_frames:
                continue
            tracks.append(Track3D(track_id=track_id_offset + len(tracks), observations=obs))

        lens = np.array([len(t.observations) for t in tracks], dtype=np.float64)
        spans = np.array(
            [max(t.observations) - min(t.observations) for t in tracks], dtype=np.float64
        ) if len(tracks) else np.zeros(1)
        self.stats = {
            "anchors": float(len(usable)),
            "pairs_tried": float(tried),
            "pairs_accepted": float(accepted),
            "inlier_matches": float(inliers_total),
            "tracks": float(len(tracks)),
            "mean_track_frames": float(lens.mean()) if len(tracks) else 0.0,
            "median_span_frames": float(np.median(spans)) if len(tracks) else 0.0,
            "contradictory_groups": float(contradictory),
        }
        self.logger.info(
            f"Wide-baseline linking: {len(usable)} anchor frames, {accepted}/{tried} pairs "
            f"verified, {inliers_total} inlier matches merged into {len(tracks)} tracks "
            f"averaging {self.stats['mean_track_frames']:.1f} frames and spanning "
            f"{self.stats['median_span_frames']:.0f} frames at the median "
            f"({contradictory} contradictory groups dropped)."
        )
        return tracks
