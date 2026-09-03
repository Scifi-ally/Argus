"""
Coarse-to-fine plane-sweep Multi-View Stereo for SinglePass3D.

Every pixel is tested against a set of depth hypotheses: the plane at that depth
induces a homography into each source view, the warped patch is compared with the
reference by zero-mean normalised cross-correlation, and the depth whose warp
matches best wins. This is what resolves facade and roof detail -- correlation is
evaluated on the actual imagery at the actual poses, so the recovered surface
follows the photographs instead of a smooth prior.

Depths are then cross-checked between views, and only pixels several cameras agree
on survive into the fused model.
"""

from __future__ import annotations
from typing import Callable, Dict, List, Optional, Sequence, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import PointMapResult, Pose3D
from singlepass3d.geometry.learned_adapters.base import BaseReconstructionAdapter
from singlepass3d.sensor.camera_model import CameraModel


def compute_normals_from_pointmap(pointmap: np.ndarray, mask: np.ndarray,
                                  stencil: int = 3) -> np.ndarray:
    """
    Dense surface normals from a pointmap via central differences.

    pointmap: (H, W, 3) camera-frame points, mask: (H, W) bool.
    Returns unit normals (H, W, 3) oriented toward the camera.

    A one-pixel central difference measures the surface across a two-pixel baseline,
    which at this working resolution is about three centimetres of surface -- the same
    order as the depth noise itself, so the tilt it reports is mostly noise. Measured on
    these frames it made a third of the otherwise valid pixels look edge-on and the
    incidence test then deleted them. The difference is taken over a wider baseline
    instead, and narrowed back to one pixel only where the wide samples straddle a depth
    discontinuity and a wide slope would be meaningless.
    """
    H, W, _ = pointmap.shape
    normals = np.zeros((H, W, 3), dtype=np.float64)
    normals[..., 2] = -1.0
    z = pointmap[..., 2]

    def diffs(k: int):
        du = np.zeros_like(pointmap)
        dv = np.zeros_like(pointmap)
        du[:, k:-k] = (pointmap[:, 2 * k:] - pointmap[:, :-2 * k]) / (2.0 * k)
        dv[k:-k, :] = (pointmap[2 * k:, :] - pointmap[:-2 * k, :]) / (2.0 * k)
        cu = np.zeros((H, W), dtype=bool)
        cv_ = np.zeros((H, W), dtype=bool)
        zc = np.maximum(np.abs(z), 1e-6)
        cu[:, k:-k] = ((z[:, 2 * k:] > 0) & (z[:, :-2 * k] > 0)
                       & (np.abs(z[:, 2 * k:] - z[:, :-2 * k]) < 0.06 * zc[:, k:-k]))
        cv_[k:-k, :] = ((z[2 * k:, :] > 0) & (z[:-2 * k, :] > 0)
                        & (np.abs(z[2 * k:, :] - z[:-2 * k, :]) < 0.06 * zc[k:-k, :]))
        return du, dv, cu & cv_

    dp_du, dp_dv, _ = diffs(1)
    s = max(1, int(stencil))
    if s > 1 and min(H, W) > 2 * s + 2:
        du_w, dv_w, ok_w = diffs(s)
        sel = ok_w[..., None]
        dp_du = np.where(sel, du_w, dp_du)
        dp_dv = np.where(sel, dv_w, dp_dv)

    n = np.cross(dp_du, dp_dv)
    norms = np.linalg.norm(n, axis=2, keepdims=True)
    valid = (norms[:, :, 0] > 1e-9) & mask
    normals[valid] = n[valid] / norms[valid]

    flip = valid & (normals[..., 2] > 0)
    normals[flip] = -normals[flip]
    return normals


def _guided_filter(guide: np.ndarray, src: np.ndarray, radius: int, eps: float) -> np.ndarray:
    """
    Edge-preserving smoothing of `src` steered by `guide`.

    Depth is smoothed only where the image is smooth, so roof edges and facade
    corners keep their discontinuities instead of being rounded off.
    """
    g = guide.astype(np.float32)
    s = src.astype(np.float32)
    k = (2 * radius + 1, 2 * radius + 1)
    mean_g = cv2.boxFilter(g, -1, k, normalize=True)
    mean_s = cv2.boxFilter(s, -1, k, normalize=True)
    corr_gg = cv2.boxFilter(g * g, -1, k, normalize=True)
    corr_gs = cv2.boxFilter(g * s, -1, k, normalize=True)
    var_g = corr_gg - mean_g * mean_g
    cov_gs = corr_gs - mean_g * mean_s
    a = cov_gs / (var_g + eps)
    b = mean_s - a * mean_g
    mean_a = cv2.boxFilter(a, -1, k, normalize=True)
    mean_b = cv2.boxFilter(b, -1, k, normalize=True)
    return mean_a * g + mean_b


def _zncc(ref: np.ndarray, warp: np.ndarray, valid: np.ndarray,
          ref_mean: np.ndarray, ref_var: np.ndarray, win: int,
          buf: Optional[dict] = None, out: Optional[np.ndarray] = None) -> np.ndarray:
    """
    Windowed zero-mean normalised cross-correlation in [-1, 1].

    Invariant to per-view gain and offset, which is what makes it usable across the
    exposure changes of a real flight.

    Called once per (hypothesis, source view) pair -- a few thousand times per depth
    map -- so every intermediate is written into a caller-owned scratch buffer rather
    than allocated. `buf` is an opaque dict the caller keeps alive across the sweep;
    omit it and the function allocates as it used to. `out`, when given, receives the
    score directly, which saves the caller a copy per source view. The arithmetic is
    unchanged.
    """
    k = (win, win)
    if buf is None:
        buf = {}
    def _b(name: str) -> np.ndarray:
        a = buf.get(name)
        if a is None or a.shape != ref.shape:
            a = np.empty(ref.shape, dtype=np.float32)
            buf[name] = a
        return a

    w, n, mean_w, var_w, t = _b("w"), _b("n"), _b("mean_w"), _b("var_w"), _b("t")
    cov = out if (out is not None and out.shape == ref.shape
                  and out.dtype == np.float32) else _b("cov")
    np.multiply(warp, valid, out=w)
    cv2.boxFilter(valid, -1, k, dst=n, normalize=True)
    np.maximum(n, np.float32(1e-3), out=n)
    cv2.boxFilter(w, -1, k, dst=mean_w, normalize=True)
    np.divide(mean_w, n, out=mean_w)
    np.multiply(w, w, out=t)
    cv2.boxFilter(t, -1, k, dst=var_w, normalize=True)
    np.divide(var_w, n, out=var_w)
    np.subtract(var_w, mean_w * mean_w, out=var_w)
    np.multiply(ref, w, out=t)
    cv2.boxFilter(t, -1, k, dst=cov, normalize=True)
    np.divide(cov, n, out=cov)
    np.subtract(cov, ref_mean * mean_w, out=cov)
    # denom reuses the w scratch: the warp product is finished with by now.
    np.maximum(var_w, np.float32(1e-6), out=var_w)
    np.multiply(np.maximum(ref_var, np.float32(1e-6)), var_w, out=w)
    np.sqrt(w, out=w)
    np.divide(cov, w, out=cov)
    cov[n < 0.55] = -1.0
    return np.clip(cov, -1.0, 1.0, out=cov)


class MVSReconstructionEngine(BaseReconstructionAdapter):
    # The runner may hand this engine source views from outside the current window.
    supports_source_pool = True

    """Dense depth from plane-sweep correlation over the real camera poses."""

    def __init__(
        self,
        device: str = "cpu",
        min_depth: float = 1.0,
        max_depth: float = 100.0,
        mvs_max_dim: int = 640,
        mvs_num_planes: int = 64,
        mvs_num_src_views: int = 3,
        mvs_levels: int = 3,
        mvs_zncc_win: int = 7,
        mvs_geo_consistency_views: int = 2,
        mvs_min_confidence: float = 0.15,
        mvs_min_cos_incidence: float = 0.18,
        mvs_min_score: float = 0.15,
        mvs_cost_radius: int = 5,
        mvs_cost_eps: float = 1e-3,
    ):
        super().__init__(device=device)
        self.min_depth = float(min_depth)
        self.max_depth = float(max_depth)
        self.max_dim = int(mvs_max_dim)
        self.num_planes = max(16, int(mvs_num_planes))
        self.num_src = max(1, int(mvs_num_src_views))
        self.levels = max(1, int(mvs_levels))
        self.win = int(mvs_zncc_win) | 1
        self.geo_views = max(0, int(mvs_geo_consistency_views))
        self.min_conf = float(mvs_min_confidence)
        # Grazing cutoff, as cos(incidence). Exposed because it is a coverage/quality
        # trade the footage decides: an oblique pass over facades needs it lower than
        # a nadir pass over roofs, and facades are half of what this system is for.
        self.min_cos_incidence = float(mvs_min_cos_incidence)
        # Radius of the cost-volume aggregation, in pixels at the working resolution,
        # and the edge threshold that steers it (as a squared intensity in [0, 1]).
        # Zero disables the aggregation and restores per-pixel winner-take-all.
        # Correlation a winning hypothesis must reach before it is believed at all.
        # This was the binding gate on this footage by a wide margin, and it was set far
        # too high: every pixel swept to a depth inside the bracket and 94% cleared the
        # margin floor, but at 0.4 only 38% of the frame correlated well enough to be
        # kept. Lowering it does not trade cleanliness for coverage, which is what a
        # threshold like this is usually assumed to do -- measured over eight frames,
        # the mesh got cleaner as it fell:
        #
        #   0.40   20% of the frame kept   996k faces   5.5% of faces in specks   546 m2
        #   0.25   26%                    1178k         5.2%                     685 m2
        #   0.15   30%                    1259k         4.3%                     759 m2
        #   0.05   33%                    1275k         5.1%                     805 m2
        #
        # because the surface a high threshold refuses is mostly low-texture roof and
        # shaded facade in the middle of otherwise good surface, so refusing it punches
        # holes and severs the mesh: the five largest connected pieces hold 74% of the
        # faces at 0.4 and 86% at 0.15. Cross-view corroboration is the referee for what
        # a weak correlation proposes, and it is a much better one than the correlation
        # score itself. It turns over at 0.05, where the specks come back and the fused
        # range agreement starts to slip, so 0.15 is the floor rather than zero.
        self.min_score = float(mvs_min_score)
        self.cost_radius = max(0, int(mvs_cost_radius))
        self.cost_eps = float(mvs_cost_eps)
        # Grey images of frames outside the current window, kept at working resolution
        # so a source view chosen for its baseline is read from disk at most once.
        self._gray_cache: Dict[int, np.ndarray] = {}
        self.logger = get_logger()
        self._prior: Optional[np.ndarray] = None

    def set_scene_prior(self, points_world: Optional[np.ndarray]) -> None:
        """
        Supplies the sparse SfM landmarks.

        The sweep only needs to cover depths the scene actually occupies; deriving
        that range per view from the landmarks makes every hypothesis count instead
        of spending most of them on empty space.
        """
        if points_world is None or len(points_world) == 0:
            self._prior = None
            return
        self._prior = np.asarray(points_world, dtype=np.float64).reshape(-1, 3)
        self.logger.info(f"MVS depth range prior installed from {len(self._prior)} SfM landmarks.")

    def _depth_range(self, pose: Pose3D) -> Tuple[float, float]:
        """Depth bracket for one view, from the landmark cloud when available."""
        lo, hi = self.min_depth, self.max_depth
        if self._prior is not None and len(self._prior) >= 20:
            z = (self._prior - pose.t_wc) @ pose.R_cw.T[:, 2] if False else \
                (pose.R_cw @ (self._prior - pose.t_wc).T).T[:, 2]
            z = z[z > 0.2]
            if len(z) >= 20:
                # Bracket in inverse depth, because that is what the sweep spaces its
                # hypotheses in. Padding a depth percentile instead spends the budget
                # unevenly: on this scene lo = p2(z) * 0.7 pushed the near end to 3.3 m
                # for a surface whose median is 10 m, and since inverse depth is 1/3.3
                # there, a third of every plane went to the empty half-metre in front of
                # the drone while the depths that matter got a 49 cm plane step at 10 m.
                iv = 1.0 / z
                iv_hi = float(np.percentile(iv, 98.0)) * 1.15
                iv_lo = float(np.percentile(iv, 2.0)) * 0.85
                if iv_hi > iv_lo > 1e-6:
                    lo, hi = 1.0 / iv_hi, 1.0 / iv_lo
        if not np.isfinite(lo) or lo <= 0.1:
            lo = self.min_depth
        if not np.isfinite(hi) or hi <= lo * 1.05:
            hi = max(lo * 3.0, self.max_depth)
        return lo, hi

    @staticmethod
    def _relative(pose_r: Pose3D, pose_s: Pose3D) -> Tuple[np.ndarray, np.ndarray]:
        """Rigid transform taking reference-camera points into the source camera."""
        R_sr = pose_s.R_cw @ pose_r.R_wc
        t_sr = pose_s.R_cw @ (pose_r.t_wc - pose_s.t_wc)
        return R_sr, t_sr

    def _gray_for(
        self,
        j: int,
        cand_ids: List[int],
        grays: List[Optional[np.ndarray]],
        provider: Optional[Callable[[int], Optional[np.ndarray]]],
        Wk: int,
        Hk: int,
    ) -> Optional[np.ndarray]:
        """Grey image for a candidate source view, fetched and cached on first use."""
        g = grays[j] if j < len(grays) else None
        if g is not None:
            return g
        if provider is None:
            return None
        fid = cand_ids[j]
        cached = self._gray_cache.get(fid)
        if cached is not None and cached.shape == (Hk, Wk):
            grays[j] = cached
            return cached
        try:
            img = provider(fid)
        except Exception:
            img = None
        if img is None:
            return None
        if img.shape[:2] != (Hk, Wk):
            img = cv2.resize(img, (Wk, Hk), interpolation=cv2.INTER_AREA)
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
        if len(self._gray_cache) > 256:
            self._gray_cache.clear()
        self._gray_cache[fid] = g
        grays[j] = g
        return g

    def _pick_sources(self, i: int, poses: List[Optional[Pose3D]]) -> List[int]:
        """
        Chooses source views for one reference frame.

        Wants baseline -- a neighbour taken from almost the same spot cannot
        triangulate anything -- while keeping the viewing direction close enough that
        the same surfaces are visible.
        """
        pr = poses[i]
        if pr is None:
            return []
        # The useful baseline is set by how far away the scene is, not by an absolute
        # distance: triangulating a facade 8 m away wants roughly a metre of baseline,
        # while the same metre is nearly useless against terrain 80 m below. Aiming at
        # a fixed distance under-triangulates close scenes and decorrelates far ones.
        lo, hi = self._depth_range(pr)
        target = float(np.clip(0.5 * (lo + hi) / 10.0, 0.15, 25.0))
        scored: List[Tuple[float, int]] = []
        axis_r = pr.R_wc[:, 2]
        for j, ps in enumerate(poses):
            if j == i or ps is None:
                continue
            b = float(np.linalg.norm(ps.t_wc - pr.t_wc))
            if b < min(0.05, target * 0.15):
                continue
            cos = float(np.dot(axis_r, ps.R_wc[:, 2]))
            if cos < 0.55:
                continue
            # Peaks at the target baseline and decays for very wide or very narrow ones.
            score = cos * np.exp(-((np.log(max(b, 1e-3) / target)) ** 2) / 1.6)
            scored.append((score, j))
        scored.sort(reverse=True)
        return [j for _, j in scored[:self.num_src]]

    def _sweep(
        self,
        gray_ref: np.ndarray,
        grays_src: List[np.ndarray],
        K_ref: np.ndarray,
        K_src: List[np.ndarray],
        rel: List[Tuple[np.ndarray, np.ndarray]],
        inv_lo: float,
        inv_hi: float,
        n_planes: int,
        init_inv: Optional[np.ndarray] = None,
        band: float = 0.0,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        One plane sweep over `n_planes` depth hypotheses.

        Returns inverse depth, the winning ZNCC, and its margin over the runner-up --
        the margin is the honest confidence signal, because a textureless wall
        correlates equally well at every depth and so produces no margin at all.

        Hypotheses are spaced uniformly in inverse depth, which is uniform in
        disparity, so no hypothesis is spent on a depth the pixels cannot resolve.
        When `init_inv` is given the sweep is a per-pixel band around it, which is
        how the finer pyramid levels add detail without re-searching everything.
        """
        H, W = gray_ref.shape
        ref = gray_ref.astype(np.float32)
        k = (self.win, self.win)
        ref_mean = cv2.boxFilter(ref, -1, k, normalize=True)
        ref_var = cv2.boxFilter(ref * ref, -1, k, normalize=True) - ref_mean * ref_mean
        # Unit-scaled so the guided filter's edge threshold means the same thing
        # whatever the exposure of the frame.
        guide = ref * np.float32(1.0 / 255.0)

        u = np.arange(W, dtype=np.float32)[None, :].repeat(H, 0)
        v = np.arange(H, dtype=np.float32)[:, None].repeat(W, 1)
        xr = (u - np.float32(K_ref[0, 2])) / np.float32(K_ref[0, 0])
        yr = (v - np.float32(K_ref[1, 2])) / np.float32(K_ref[1, 1])

        if init_inv is None:
            offsets = np.linspace(inv_lo, inv_hi, n_planes)
            step = float((inv_hi - inv_lo) / max(1, n_planes - 1))
        else:
            offsets = np.linspace(-band, band, n_planes)
            step = float(2.0 * band / max(1, n_planes - 1))

        best = np.full((H, W), -2.0, dtype=np.float32)
        second = np.full((H, W), -2.0, dtype=np.float32)
        best_inv = np.zeros((H, W), dtype=np.float32)
        best_idx = np.full((H, W), -9.0, dtype=np.float32)
        second_idx = np.full((H, W), -9.0, dtype=np.float32)
        s_left = np.zeros((H, W), dtype=np.float32)
        s_right = np.zeros((H, W), dtype=np.float32)
        s_prev: Optional[np.ndarray] = None
        prev_improved: Optional[np.ndarray] = None
        n_src = max(1, len(grays_src))
        keep = int(np.ceil(n_src / 2.0))
        # One buffer per source view plus one spare, every one of them standalone and
        # interchangeable. The compare-exchange network below moves buffers by pointer
        # rather than copying their contents, so a score buffer and the spare have to be
        # the same kind of thing -- rows of a single (n_src, H, W) array are not, and
        # rotating a row view into the spare slot would have the network overwrite a
        # score it had not yet read.
        spool = [np.empty((H, W), dtype=np.float32) for _ in range(n_src + 1)]

        # Everything about the warp that does not depend on the depth hypothesis is
        # computed here, once, instead of inside the sweep.
        #
        # The reprojection of a pixel at depth Z is R @ (xr*Z, yr*Z, Z) + t, which is
        # (R @ (xr, yr, 1)) * Z + t: the rotated ray direction is a property of the
        # pixel and the pose, not of the hypothesis. Rolling the source focal length
        # into it as well leaves two multiply-adds and a divide per hypothesis, on
        # buffers that are allocated once. Previously each of the thousand-odd
        # (hypothesis, view) pairs rebuilt X, Y, Zs, Xs, Ys and re-converted the
        # source image to float -- some forty passes over a half-megapixel grid, all
        # of them allocating. Same warp, same scores; a third of the arithmetic.
        srcf: List[np.ndarray] = [np.ascontiguousarray(g, dtype=np.float32) for g in grays_src]
        rays: List[Tuple[np.ndarray, np.ndarray, np.ndarray, float, float, float, float, float]] = []
        for si in range(len(grays_src)):
            R, t = rel[si]
            Ks = K_src[si]
            a2 = np.float32(R[2, 0]) * xr + np.float32(R[2, 1]) * yr + np.float32(R[2, 2])
            p0 = np.float32(Ks[0, 0]) * (np.float32(R[0, 0]) * xr
                                         + np.float32(R[0, 1]) * yr + np.float32(R[0, 2]))
            p1 = np.float32(Ks[1, 1]) * (np.float32(R[1, 0]) * xr
                                         + np.float32(R[1, 1]) * yr + np.float32(R[1, 2]))
            rays.append((a2, p0, p1,
                         float(t[2]), float(Ks[0, 0] * t[0]), float(Ks[1, 1] * t[1]),
                         float(Ks[0, 2]), float(Ks[1, 2])))

        Zbuf = np.empty((H, W), dtype=np.float32)
        Zs = np.empty((H, W), dtype=np.float32)
        safe = np.empty((H, W), dtype=np.float32)
        mx = np.empty((H, W), dtype=np.float32)
        my = np.empty((H, W), dtype=np.float32)
        inb = np.empty((H, W), dtype=bool)
        tb = np.empty((H, W), dtype=bool)
        validf = np.empty((H, W), dtype=np.float32)
        zbuf: dict = {}
        # A bubble compare-exchange network: n(n-1)/2 fixed index pairs that sort any
        # input, so the top `keep` planes end up in the last `keep` slots.
        sel_net = [(j, j + 1) for i in range(n_src) for j in range(n_src - 1 - i)]
        sel_acc = np.empty((H, W), dtype=np.float32)

        for t_idx, o in enumerate(offsets):
            if init_inv is None:
                inv = np.float32(o)
                Z = np.float32(1.0 / max(1e-6, float(o)))
            else:
                inv = np.clip(init_inv + np.float32(o), inv_lo, inv_hi)
                np.maximum(inv, np.float32(1e-6), out=Zbuf)
                np.divide(np.float32(1.0), Zbuf, out=Zbuf)
                Z = Zbuf

            for si in range(len(grays_src)):
                a2, p0, p1, t2, q0, q1, cx, cy = rays[si]
                np.multiply(a2, Z, out=Zs)
                np.add(Zs, np.float32(t2), out=Zs)
                # Guard the divide without changing which pixels survive: anything
                # with |Zs| under the guard fails the Zs > 0.05 bounds test anyway.
                np.abs(Zs, out=safe)
                np.maximum(safe, np.float32(1e-4), out=safe)
                np.copysign(safe, Zs, out=safe)
                np.multiply(p0, Z, out=mx)
                np.add(mx, np.float32(q0), out=mx)
                np.divide(mx, safe, out=mx)
                np.add(mx, np.float32(cx), out=mx)
                np.multiply(p1, Z, out=my)
                np.add(my, np.float32(q1), out=my)
                np.divide(my, safe, out=my)
                np.add(my, np.float32(cy), out=my)
                np.greater(Zs, np.float32(0.05), out=inb)
                np.greater_equal(mx, np.float32(0.0), out=tb)
                np.logical_and(inb, tb, out=inb)
                np.less_equal(mx, np.float32(W - 1), out=tb)
                np.logical_and(inb, tb, out=inb)
                np.greater_equal(my, np.float32(0.0), out=tb)
                np.logical_and(inb, tb, out=inb)
                np.less_equal(my, np.float32(H - 1), out=tb)
                np.logical_and(inb, tb, out=inb)
                warped = cv2.remap(srcf[si], mx, my, cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=0)
                np.copyto(validf, inb)
                _zncc(ref, warped, validf, ref_mean, ref_var, self.win, zbuf, spool[si])

            # Averaging only the better half tolerates a source view in which the
            # surface is occluded, without letting it veto a correct depth.
            #
            # Which half is all this needs, not their order, and neither sorting nor
            # partitioning six views is the way to get it: both read six values that
            # sit two megabytes apart for every pixel, and that stride costs more than
            # the comparisons. A fixed compare-exchange network sweeps the views
            # against each other instead -- whole planes at a time, in cache order,
            # writing through pointers rather than copying -- and lands on bit-identical
            # values in a fifth of the time.
            if n_src > 1:
                for ci, cj in sel_net:
                    np.minimum(spool[ci], spool[cj], out=spool[n_src])
                    np.maximum(spool[ci], spool[cj], out=spool[cj])
                    spool[ci], spool[n_src] = spool[n_src], spool[ci]
                score = sel_acc
                score[...] = spool[n_src - keep]
                for i in range(n_src - keep + 1, n_src):
                    np.add(score, spool[i], out=score)
                np.divide(score, np.float32(keep), out=score)
            else:
                score = spool[0]

            if self.cost_radius > 0:
                # Aggregate each hypothesis across the image before any of them wins.
                # A correlation window on its own decides every pixel independently, so
                # on a shaded facade or a flat roof -- where the window is nearly as
                # ambiguous as a single pixel -- the winner is whichever hypothesis the
                # noise happened to favour. Measured on these eight frames, that is not
                # a small effect: 60% of the frame never reached a confident correlation
                # at all, and of what did, 22% was contradicted outright by another view
                # by more than 20 cm. Neither is a tolerance to be loosened; both are
                # the argmax being unconstrained.
                #
                # Letting neighbouring pixels vote on the same hypothesis is the classic
                # remedy, and steering the vote by the reference image is what keeps it
                # from flattening the model: support crosses a textureless region freely
                # and stops at the intensity edge where the roofline is, so a facade
                # inherits the depth of the facade rather than of the sky behind it.
                # It costs a few box filters per hypothesis against six warps and six
                # correlations, so the aggregation is close to free.
                score = _guided_filter(guide, score, self.cost_radius, self.cost_eps)

            if prev_improved is not None:
                s_right = np.where(prev_improved, score, s_right)
            improved = score > best
            ti = np.float32(t_idx)

            # The runner-up must be a genuinely different depth, not the neighbouring
            # hypothesis. On a well-textured surface the adjacent plane correlates
            # almost as well, so counting it would report zero confidence everywhere.
            demote = improved & (np.abs(best_idx - ti) > 1.5) & (best > second)
            second = np.where(demote, best, second)
            second_idx = np.where(demote, best_idx, second_idx)
            rival = (~improved) & (np.abs(ti - best_idx) > 1.5) & (score > second)
            second = np.where(rival, score, second)
            second_idx = np.where(rival, ti, second_idx)

            if s_prev is not None:
                s_left = np.where(improved, s_prev, s_left)
            best_inv = np.where(improved, inv, best_inv).astype(np.float32)
            best = np.where(improved, score, best)
            best_idx = np.where(improved, ti, best_idx)
            stale = np.abs(second_idx - best_idx) <= 1.5
            second = np.where(stale, -2.0, second).astype(np.float32)
            second_idx = np.where(stale, -9.0, second_idx).astype(np.float32)
            s_prev, prev_improved = score.copy(), improved

        # Sub-hypothesis refinement: a parabola through the winner and its two
        # neighbours. Without it surfaces come out visibly terraced at the plane
        # spacing rather than continuous.
        denom = s_left - 2.0 * best + s_right
        usable = (np.abs(denom) > 1e-6) & (s_left > -1.9) & (s_right > -1.9)
        delta = np.where(usable, 0.5 * (s_left - s_right) / np.where(usable, denom, 1.0), 0.0)
        best_inv = np.clip(best_inv + np.clip(delta, -0.5, 0.5).astype(np.float32) * np.float32(step),
                           inv_lo, inv_hi)
        return best_inv, best, np.clip(best - second, 0.0, 2.0)

    def _estimate_depth(
        self,
        gray_ref: np.ndarray,
        grays_src: List[np.ndarray],
        K_ref: np.ndarray,
        K_src: List[np.ndarray],
        rel: List[Tuple[np.ndarray, np.ndarray]],
        lo: float,
        hi: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Coarse-to-fine depth for one reference frame.

        The coarse level searches the whole depth range cheaply and unambiguously;
        each finer level re-searches only a narrow band around it at double the
        resolution, which is where the small structure appears.
        """
        inv_lo, inv_hi = 1.0 / hi, 1.0 / lo
        inv_depth: Optional[np.ndarray] = None
        score = margin = None

        for level in range(self.levels):
            f = 0.5 ** (self.levels - 1 - level)
            Hl = max(32, int(round(gray_ref.shape[0] * f)))
            Wl = max(32, int(round(gray_ref.shape[1] * f)))
            gr = cv2.resize(gray_ref, (Wl, Hl), interpolation=cv2.INTER_AREA)
            gss = [cv2.resize(g, (Wl, Hl), interpolation=cv2.INTER_AREA) for g in grays_src]
            sx, sy = Wl / gray_ref.shape[1], Hl / gray_ref.shape[0]
            S = np.diag([sx, sy, 1.0])
            Kr = S @ K_ref
            Kss = [S @ Ks for Ks in K_src]

            if inv_depth is None:
                n_planes = self.num_planes
                init = None
                band = 0.0
            else:
                inv_depth = cv2.resize(inv_depth, (Wl, Hl), interpolation=cv2.INTER_LINEAR)
                # The refinement levels re-search a band around the coarse winner, so
                # their cost is set by how finely that band is divided and not by how
                # wide the coarse search was. Tying their plane count to the coarse
                # budget therefore made a denser coarse search pay twice, at full
                # resolution, for hypotheses it did not need; capped here so the coarse
                # level can be made as dense as the depth precision warrants.
                n_planes = int(np.clip(self.num_planes // 3, 15, 24))
                init = inv_depth
                band = 3.0 * (inv_hi - inv_lo) / max(1, self.num_planes - 1) * (0.5 ** level)

            inv_depth, score, margin = self._sweep(
                gr, gss, Kr, Kss, rel, inv_lo, inv_hi, n_planes, init, band
            )
            # Steer the smoothing by the image so depth edges stay on image edges.
            inv_depth = _guided_filter(gr.astype(np.float32) / 255.0, inv_depth,
                                       radius=3, eps=1e-4).astype(np.float32)

        depth = 1.0 / np.maximum(inv_depth, 1e-6)
        return depth.astype(np.float32), score, margin

    def _geometric_consistency(
        self,
        depths: List[Optional[np.ndarray]],
        Ks: List[Optional[np.ndarray]],
        poses: List[Optional[Pose3D]],
        i: int,
        neighbours: List[int],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Counts how many other views independently measured the same surface point.

        A depth that only one camera believes is usually a correlation artefact --
        repeated texture, a moving car, a specular roof. Requiring agreement is what
        keeps those out of the fused model instead of smoothing them away later.

        Returns (agreements, confirmable_views, summed agreeing depth, count). The
        second count matters: a pixel near
        the frame border, or one whose neighbours had no reliable depth there, simply
        cannot be confirmed twice, and deleting it would punch holes in the model for
        a reason that has nothing to do with whether the depth is right.
        """
        d_ref, K_ref, p_ref = depths[i], Ks[i], poses[i]
        H, W = d_ref.shape
        agree = np.zeros((H, W), dtype=np.int32)
        seen = np.zeros((H, W), dtype=np.int32)
        fused = np.zeros((H, W), dtype=np.float32)
        nfused = np.zeros((H, W), dtype=np.float32)

        u = np.arange(W, dtype=np.float32)[None, :].repeat(H, 0)
        v = np.arange(H, dtype=np.float32)[:, None].repeat(W, 1)
        xr = (u - np.float32(K_ref[0, 2])) / np.float32(K_ref[0, 0])
        yr = (v - np.float32(K_ref[1, 2])) / np.float32(K_ref[1, 1])
        pts_w = np.stack([xr * d_ref, yr * d_ref, d_ref], axis=-1) @ p_ref.R_wc.T + p_ref.t_wc

        for j in neighbours:
            d_j, K_j, p_j = depths[j], Ks[j], poses[j]
            if d_j is None or K_j is None or p_j is None or d_j.shape != (H, W):
                continue
            pc = (pts_w - p_j.t_wc) @ p_j.R_cw.T
            z = pc[..., 2]
            ok = z > 0.05
            mx = (np.float32(K_j[0, 0]) * (pc[..., 0] / np.where(ok, z, 1.0))
                  + np.float32(K_j[0, 2])).astype(np.float32)
            my = (np.float32(K_j[1, 1]) * (pc[..., 1] / np.where(ok, z, 1.0))
                  + np.float32(K_j[1, 2])).astype(np.float32)
            ok &= (mx >= 0) & (mx <= W - 1) & (my >= 0) & (my <= H - 1)
            # Nearest sampling: these depth maps have holes, and interpolating across
            # a hole invents a depth halfway to zero that then fails the agreement test.
            d_samp = cv2.remap(d_j, mx, my, cv2.INTER_NEAREST,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            # Depth tolerance grows with range: 1 % of the distance is roughly the
            # triangulation precision the geometry can deliver.
            tol = np.maximum(0.05, 0.02 * z)
            usable = ok & (d_samp > 0)
            hit = usable & (np.abs(d_samp - z) < tol)
            seen += usable.astype(np.int32)
            agree += hit.astype(np.int32)
            # Every view that agrees has measured this surface independently, from its
            # own baseline and its own pixel grid, so their samples straddle the truth
            # rather than repeating one map's error. Averaging them is the cheapest
            # precision available here -- the reprojections are already computed, and
            # noise falls as the root of the count -- and precision along the line of
            # sight is exactly what the TSDF voxel is sized by.
            fused += np.where(hit, d_samp, 0.0).astype(np.float32)
            nfused += hit.astype(np.float32)
        return agree, seen, fused, nfused

    def reconstruct_window(
        self,
        frames: List[np.ndarray],
        frame_ids: List[int],
        camera: CameraModel,
        initial_poses: Optional[List[Pose3D]] = None,
        source_pool: Optional[Sequence[Tuple[int, Optional[Pose3D]]]] = None,
        image_provider: Optional[Callable[[int], Optional[np.ndarray]]] = None,
    ) -> List[PointMapResult]:
        n = len(frames)
        if n == 0:
            return []
        poses: List[Optional[Pose3D]] = list(initial_poses or [None] * n)
        poses += [None] * (n - len(poses))

        if sum(p is not None for p in poses) < 2:
            self.logger.warning(
                "Plane-sweep MVS needs at least two posed frames in the window; skipping it."
            )
            return []

        # Work at a fixed resolution so cost and memory are predictable.
        h0, w0 = frames[0].shape[:2]
        f = min(1.0, self.max_dim / float(max(h0, w0)))
        Wk, Hk = int(round(w0 * f)), int(round(h0 * f))
        cam_k = camera.scale_to_resolution(Wk, Hk)
        K = np.asarray(cam_k.K, dtype=np.float64)

        small = [cv2.resize(img, (Wk, Hk), interpolation=cv2.INTER_AREA) for img in frames]
        grays: List[Optional[np.ndarray]] = [cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) for img in small]

        # Source views may come from outside this window. A window is a memory and
        # streaming boundary, not a geometric one, and on a slow pass every frame inside
        # one sits within a few tens of centimetres of the others. Depth error falls off
        # in proportion to the baseline, so triangulating only within a window discards
        # most of the geometry the flight actually flew: here the window offers 0.2 m
        # where the pass covers 3 m. Candidates from the rest of the flight are listed
        # after the window's own frames and their images are pulled in only if chosen.
        cand_poses: List[Optional[Pose3D]] = list(poses)
        cand_ids: List[int] = [int(f) for f in frame_ids]
        if source_pool:
            have = set(cand_ids)
            for fid, ps in source_pool:
                if ps is None or int(fid) in have:
                    continue
                have.add(int(fid))
                cand_ids.append(int(fid))
                cand_poses.append(ps)
                grays.append(None)
        m = len(cand_ids)
        depths: List[Optional[np.ndarray]] = [None] * m
        scores: List[Optional[np.ndarray]] = [None] * m
        margins: List[Optional[np.ndarray]] = [None] * m
        srcs: List[List[int]] = [[] for _ in range(m)]
        # Baseline actually achieved, per source view. Triangulated depth error is
        # roughly range / baseline * matching error, so this ratio -- not the image
        # resolution -- sets how much relief a pass can physically resolve.
        baselines: List[float] = []

        self.logger.info(
            f"Plane-sweep MVS: {n} frames at {Wk}x{Hk}, {self.num_planes} planes, "
            f"{self.levels} pyramid levels, up to {self.num_src} source views."
        )
        for i in range(n):
            if poses[i] is None:
                continue
            picked = self._pick_sources(i, cand_poses)
            gs: List[np.ndarray] = []
            keep_src: List[int] = []
            for j in picked:
                g = self._gray_for(j, cand_ids, grays, image_provider, Wk, Hk)
                if g is not None:
                    gs.append(g)
                    keep_src.append(j)
            srcs[i] = keep_src
            if not gs:
                continue
            baselines.extend(
                float(np.linalg.norm(poses[i].t_wc - cand_poses[j].t_wc)) for j in keep_src
            )
            lo, hi = self._depth_range(poses[i])
            rel = [self._relative(poses[i], cand_poses[j]) for j in srcs[i]]
            depths[i], scores[i], margins[i] = self._estimate_depth(
                grays[i], gs, K, [K] * len(gs), rel, lo, hi
            )

        Ks: List[Optional[np.ndarray]] = [K if d is not None else None for d in depths]

        # Photometric gate first, for every frame, so the cross-view test below compares
        # depths that each view already believes rather than raw argmax noise.
        confs: List[Optional[np.ndarray]] = [None] * m
        base: List[Optional[np.ndarray]] = [None] * m
        filt: List[Optional[np.ndarray]] = [None] * m
        gate = np.zeros(4, dtype=np.float64)
        for i in range(n):
            if depths[i] is None:
                continue
            lo, hi = self._depth_range(poses[i])
            score, margin = scores[i], margins[i]
            # Confidence blends how well the winning depth correlated with how
            # decisively it beat depths that are not merely its neighbours.
            corr = np.clip(0.5 * (score + 1.0), 0.0, 1.0)
            decisive = np.clip(0.45 + 0.55 * np.clip(margin / 0.12, 0.0, 1.0), 0.0, 1.0)
            confs[i] = np.clip(corr * decisive, 0.0, 1.0)
            in_range = (depths[i] > lo * 0.9) & (depths[i] < hi * 1.1)
            base[i] = in_range & (score > self.min_score) & (confs[i] > self.min_conf)
            # Which half of the gate is binding decides what to do about it. A depth
            # that fell outside the bracket means the sweep never offered the right
            # hypothesis; a weak correlation means the imagery could not choose between
            # the ones it did offer; a weak margin means it correlated everywhere.
            gate[0] += float(in_range.mean())
            gate[1] += float((in_range & (score > self.min_score)).mean())
            gate[2] += float((in_range & (confs[i] > self.min_conf)).mean())
            gate[3] += 1.0
            # Corroboration is tested against every depth that is merely in range, not
            # only against the ones that passed their own photometric gate. A neighbour
            # that failed its gate has still measured something independently, and a
            # wrong depth does not land within a couple of per cent of the reference by
            # accident. Gating first is what left half the frame with nothing able to
            # confirm it -- the gate fails in the same low-texture places in every view,
            # so the holes line up and delete real surface.
            filt[i] = np.where(in_range, depths[i], 0.0).astype(np.float32)

        results: List[PointMapResult] = []
        # Where coverage is lost matters as much as how much: a photometric gate that
        # rejects half the frame is a texture or exposure problem, while losses at the
        # cross-view test are a pose or baseline problem, and the two need opposite fixes.
        attrition = np.zeros(4, dtype=np.float64)
        blind = np.zeros(2, dtype=np.float64)
        u = np.arange(Wk, dtype=np.float32)[None, :].repeat(Hk, 0)
        v = np.arange(Hk, dtype=np.float32)[:, None].repeat(Wk, 1)
        xr = (u - np.float32(K[0, 2])) / np.float32(K[0, 0])
        yr = (v - np.float32(K[1, 2])) / np.float32(K[1, 1])

        for i in range(n):
            if depths[i] is None:
                continue
            depth = depths[i]
            conf = confs[i]
            mask = base[i].copy()
            attrition[0] += float(mask.mean())

            if self.geo_views > 0:
                # Corroboration needs frames that carry their own depth map, and the
                # source views no longer supply them: sources are chosen for baseline
                # and may come from anywhere in the flight, while depth is only solved
                # for the reference frames of this window. Tying the two together left
                # wide-baseline references with one checker or none, so the check is
                # filled out from the nearest reference frames that do have depth --
                # nearest, because those see the most of the same surface.
                want = max(2, self.geo_views + 1)
                neigh = [j for j in srcs[i] if j < n and filt[j] is not None]
                if len(neigh) < want:
                    rest = [
                        j for j in range(n)
                        if j != i and j not in neigh and filt[j] is not None
                        and cand_poses[j] is not None
                    ]
                    rest.sort(key=lambda j: float(
                        np.linalg.norm(poses[i].t_wc - cand_poses[j].t_wc)
                    ))
                    neigh += rest[: want - len(neigh)]
                neigh = neigh[:want]
                if neigh:
                    agree, seen, fsum, fcnt = self._geometric_consistency(
                        filt, Ks, cand_poses, i, neigh)
                    # Two independent confirmations are worth demanding wherever they
                    # are actually available. Where fewer neighbours could see the pixel
                    # at all -- near a frame border, or where a neighbour has its own
                    # hole -- insisting on two deletes surface for a reason that has
                    # nothing to do with whether the depth is right, and on a single
                    # pass with short baselines that covers most of the frame. Measured
                    # here it recovered 29% -> 31% of the frame at unchanged cross-view
                    # agreement, and cut the detached-fragment count with it.
                    strong = np.int32(max(1, min(2, self.geo_views)))
                    need = np.where(seen >= 3, strong, np.int32(1))
                    need = np.minimum(need, np.maximum(seen, 1)).astype(np.int32)
                    # Separating the two ways a pixel fails this test, because they call
                    # for opposite fixes: nothing could see it, versus something saw it
                    # and measured a different surface.
                    blind[0] += float((mask & (seen < 1)).mean())
                    blind[1] += float((mask & (seen >= 1) & (agree < need)).mean())
                    mask &= (agree >= need) & (seen >= 1)
                    # An unconfirmed depth is not necessarily wrong, but it is weaker
                    # evidence; fusion weights it accordingly.
                    conf = conf * np.clip(0.55 + 0.45 * (agree / np.maximum(need, 1)), 0.0, 1.0)
                    # The reference keeps its own weight of one against the views that
                    # confirmed it, so a pixel two views agree with is the mean of three
                    # independent measurements rather than being overwritten by them.
                    depth = np.where(fcnt > 0.0,
                                     (depth + fsum) / (fcnt + 1.0),
                                     depth).astype(np.float32)

            attrition[1] += float(mask.mean())
            # Isolated survivors are noise, not structure.
            keep = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN,
                                    np.ones((3, 3), np.uint8))
            mask = keep.astype(bool)
            attrition[2] += float(mask.mean())

            pts_cam = np.stack([xr * depth, yr * depth, depth], axis=-1).astype(np.float64)
            normals_cam = compute_normals_from_pointmap(pts_cam, mask)

            # A surface seen edge-on is foreshortened so severely that the correlation
            # window straddles metres of depth, and the winning hypothesis is then
            # confidently wrong. Measured on the far periphery of a nadir frame: the
            # reliable core sits at cos(incidence) 0.93, the failures at 0.2.
            # The cutoff sits at 0.18 rather than 0.30 because 0.30 was discarding
            # surface that does survive corroboration. Measured, same eight frames:
            # 0.30 kept 21% of the frame and fused at 4.3 cm; 0.18 kept 25% and fused
            # at 4.6 cm, +28% faces, and the added area is continuous sheet in the
            # render rather than skirting. Grazing samples agree slightly worse, which
            # is why the voxel moved -- the planner measured that and gave up 0.3 cm of
            # resolution for a quarter more surface. Facades are seen obliquely by
            # definition, so this is where they come from.
            view = pts_cam / np.maximum(1e-9, np.linalg.norm(pts_cam, axis=-1, keepdims=True))
            cos_incidence = np.abs(np.sum(normals_cam * view, axis=-1))
            mask &= cos_incidence > self.min_cos_incidence
            attrition[3] += float(mask.mean())

            pose = poses[i]
            pts_w = pts_cam.reshape(-1, 3) @ pose.R_wc.T + pose.t_wc
            nrm_w = normals_cam.reshape(-1, 3) @ pose.R_wc.T

            results.append(PointMapResult(
                frame_id=frame_ids[i],
                points=pts_w.reshape(Hk, Wk, 3),
                normals=nrm_w.reshape(Hk, Wk, 3),
                colors=small[i].copy(),
                confidences=conf.astype(np.float64),
                mask=mask,
                camera_pose=pose,
                depth=np.where(mask, depth, 0.0).astype(np.float32),
                K=K.copy(),
            ))

        if results:
            cov = float(np.mean([r.mask.mean() for r in results]))
            med = float(np.median([np.median(r.depth[r.mask]) for r in results if r.mask.any()]))
            a = attrition / len(results) * 100.0
            self.logger.info(
                f"Plane-sweep MVS produced {len(results)} depth maps, "
                f"{cov * 100:.1f}% mean valid pixels, median depth {med:.1f} m."
            )
            bl = blind / len(results) * 100.0
            self.logger.info(
                f"  coverage: {a[0]:.0f}% photometric -> {a[1]:.0f}% cross-view agreed -> "
                f"{a[2]:.0f}% connected -> {a[3]:.0f}% facing the camera."
            )
            self.logger.info(
                f"  cross-view loss: {bl[0]:.0f}% of the frame had no view able to check "
                f"it, {bl[1]:.0f}% was checked and disagreed."
            )
            if gate[3] > 0:
                g = gate[:3] / gate[3] * 100.0
                self.logger.info(
                    f"  photometric gate: {g[0]:.0f}% of the frame swept to a depth in "
                    f"range, {g[1]:.0f}% of it correlated above {self.min_score:.2f}, "
                    f"{g[2]:.0f}% cleared "
                    f"the margin floor."
                )
            if baselines:
                b = float(np.median(baselines))
                # A pixel-accurate match at range z with baseline b lands within
                # roughly z / (b * f_px) of the truth, so quote the ratio the flight
                # actually offered: 1:10 is a healthy MVS pass, 1:40 resolves nothing.
                self.logger.info(
                    f"  triangulation: median baseline {b:.2f} m at {med:.1f} m range "
                    f"(1:{med / max(b, 1e-6):.0f}), depth precision "
                    f"~{med * med / max(b * float(K[0, 0]), 1e-6) * 100.0:.1f} cm per matched pixel."
                )
        return results
