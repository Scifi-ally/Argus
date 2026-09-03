"""
Incremental Structure-from-Motion for SinglePass3D.

The flight logs of a single-pass survey carry GPS position but frequently no
attitude, so the fused telemetry trajectory assigns every frame an identical
rotation, which makes dense stereo geometrically meaningless. This module
recovers camera rotations and relative translations from the imagery alone
(essential-matrix seeding, PnP resection, multi-view triangulation, bundle
adjustment) and only then uses GPS to fix metric scale and georeference.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import Pose3D, Track3D, Trajectory
from singlepass3d.core.types import quat_slerp, quat_to_rot, rot_to_quat
from singlepass3d.sensor.camera_model import CameraModel

_USAC = getattr(cv2, "USAC_MAGSAC", cv2.RANSAC)
_SQPNP = getattr(cv2, "SOLVEPNP_SQPNP", cv2.SOLVEPNP_EPNP)


class _View:
    """One registered camera: world-to-camera rotation vector and translation."""
    __slots__ = ("frame_id", "rvec", "tvec")

    def __init__(self, frame_id: int, rvec: np.ndarray, tvec: np.ndarray):
        self.frame_id = int(frame_id)
        self.rvec = np.asarray(rvec, dtype=np.float64).reshape(3)
        self.tvec = np.asarray(tvec, dtype=np.float64).reshape(3)

    @property
    def R_cw(self) -> np.ndarray:
        return cv2.Rodrigues(self.rvec)[0]

    @property
    def center(self) -> np.ndarray:
        return -self.R_cw.T @ self.tvec

    def P(self, K: np.ndarray) -> np.ndarray:
        return K @ np.hstack([self.R_cw, self.tvec.reshape(3, 1)])


class IncrementalSfM:
    """
    Recovers a metrically scaled, georeferenced trajectory from feature tracks.

    Returns the trajectory, the triangulated landmark cloud (later reused as a
    depth prior for dense stereo) and statistics for the quality report.
    """

    def __init__(
        self,
        camera: CameraModel,
        min_track_len: int = 3,
        max_reproj_px: float = 2.0,
        min_tri_angle_deg: float = 1.0,
        max_ba_landmarks: int = 12000,
        max_obs_per_landmark: int = 24,
        ba_every: int = 12,
        ba_window: int = 30,
        global_ba_every: int = 5,
    ):
        self.camera = camera
        self.K = np.asarray(camera.K, dtype=np.float64)
        self.min_track_len = max(2, int(min_track_len))
        self.max_reproj_px = float(max_reproj_px)
        self.min_tri_angle = np.radians(float(min_tri_angle_deg))
        self.max_ba_landmarks = int(max_ba_landmarks)
        self.max_obs_per_landmark = max(4, int(max_obs_per_landmark))
        self.ba_every = max(4, int(ba_every))
        # Cameras kept free during an incremental refinement, and how many of those
        # refinements pass before a full global solve absorbs the accumulated drift.
        self.ba_window = max(8, int(ba_window))
        self.global_ba_every = max(1, int(global_ba_every))
        self.logger = get_logger()

        self._obs: Dict[int, Dict[int, np.ndarray]] = {}
        self._by_frame: Dict[int, Dict[int, np.ndarray]] = {}
        self._views: Dict[int, _View] = {}
        self._points: Dict[int, np.ndarray] = {}

    def _ingest(self, frame_ids: Sequence[int], tracks: Sequence[Track3D]) -> None:
        keep = set(int(f) for f in frame_ids)
        for tr in tracks:
            obs = {int(f): np.asarray(uv, dtype=np.float64).reshape(2)
                   for f, uv in tr.observations.items() if int(f) in keep}
            if len(obs) < self.min_track_len:
                continue
            tid = int(tr.track_id)
            self._obs[tid] = obs
            for f, uv in obs.items():
                self._by_frame.setdefault(f, {})[tid] = uv

    def _shared(self, f1: int, f2: int) -> List[int]:
        a, b = self._by_frame.get(f1), self._by_frame.get(f2)
        if not a or not b:
            return []
        return list(a.keys() & b.keys())

    def _seed_pair(self, frame_ids: Sequence[int]):
        """
        Picks the initial pair: many shared tracks plus enough image motion for a
        well-conditioned essential matrix, preferring pairs early in the flight.
        """
        candidates: List[Tuple[float, int, int]] = []
        n = len(frame_ids)
        for i in range(min(n - 1, 40)):
            for gap in (4, 7, 10, 14, 20):
                j = i + gap
                if j >= n:
                    continue
                ids = self._shared(frame_ids[i], frame_ids[j])
                if len(ids) < 60:
                    continue
                p1 = np.array([self._by_frame[frame_ids[i]][t] for t in ids])
                p2 = np.array([self._by_frame[frame_ids[j]][t] for t in ids])
                motion = float(np.median(np.linalg.norm(p2 - p1, axis=1)))
                if motion < 5.0:
                    continue
                candidates.append((len(ids) * min(motion, 60.0), i, j))
        candidates.sort(reverse=True)

        for _, i, j in candidates[:12]:
            f1, f2 = frame_ids[i], frame_ids[j]
            ids = self._shared(f1, f2)
            p1 = np.array([self._by_frame[f1][t] for t in ids], dtype=np.float64)
            p2 = np.array([self._by_frame[f2][t] for t in ids], dtype=np.float64)
            E, emask = cv2.findEssentialMat(p1, p2, self.K, method=_USAC,
                                            prob=0.9999, threshold=1.2)
            if E is None or E.shape != (3, 3):
                continue
            emask = emask.ravel().astype(bool) if emask is not None else np.ones(len(ids), bool)
            if int(emask.sum()) < 50:
                continue
            _, R, t, pmask = cv2.recoverPose(E, p1[emask], p2[emask], self.K)
            inl = np.asarray(ids)[emask][pmask.ravel() > 0]
            if len(inl) < 40:
                continue
            return (f1, f2, [int(x) for x in inl],
                    np.asarray(R, np.float64), np.asarray(t, np.float64).reshape(3))
        return None

    def _triangulate(self, track_ids: Sequence[int]) -> Dict[int, np.ndarray]:
        """
        Multi-view DLT triangulation, batched over tracks sharing a view count.

        Rejects points behind any camera, points that reproject badly, and points
        whose viewing rays are too parallel for the depth to mean anything.
        """
        groups: Dict[int, List[Tuple[int, List[int]]]] = {}
        for tid in track_ids:
            obs = self._obs.get(tid)
            if obs is None:
                continue
            fl = [f for f in obs if f in self._views]
            if len(fl) < 2:
                continue
            groups.setdefault(len(fl), []).append((tid, fl))

        out: Dict[int, np.ndarray] = {}
        Pcache = {f: v.P(self.K) for f, v in self._views.items()}
        Rcache = {f: v.R_cw for f, v in self._views.items()}
        Ccache = {f: v.center for f, v in self._views.items()}

        for v_count, items in groups.items():
            N = len(items)
            A = np.zeros((N, 2 * v_count, 4), dtype=np.float64)
            for r, (tid, fl) in enumerate(items):
                for k, f in enumerate(fl):
                    P = Pcache[f]
                    u, v = self._obs[tid][f]
                    A[r, 2 * k] = u * P[2] - P[0]
                    A[r, 2 * k + 1] = v * P[2] - P[1]
            A /= np.maximum(1e-12, np.linalg.norm(A, axis=2, keepdims=True))
            _, _, Vt = np.linalg.svd(A, full_matrices=False)
            Xh = Vt[:, -1, :]
            w = Xh[:, 3]
            ok = np.abs(w) > 1e-9
            X = np.zeros((N, 3))
            X[ok] = Xh[ok, :3] / w[ok, None]

            for r, (tid, fl) in enumerate(items):
                if not ok[r]:
                    continue
                Xw = X[r]
                good, errs, dirs = True, [], []
                for f in fl:
                    pc = Rcache[f] @ Xw + self._views[f].tvec
                    if pc[2] <= 0.05:
                        good = False
                        break
                    uv = self.K[:2, :2] @ (pc[:2] / pc[2]) + self.K[:2, 2]
                    errs.append(float(np.linalg.norm(uv - self._obs[tid][f])))
                    d = Xw - Ccache[f]
                    dirs.append(d / max(1e-12, float(np.linalg.norm(d))))
                if not good or float(np.mean(errs)) > self.max_reproj_px * 2.0:
                    continue
                D = np.asarray(dirs)
                if np.arccos(np.clip(float((D @ D.T).min()), -1.0, 1.0)) < self.min_tri_angle:
                    continue
                out[tid] = Xw
        return out

    def _resection(self, fid: int) -> Optional[_View]:
        """Solves one new camera from its 2D-3D correspondences (PnP + LM refine)."""
        obs = self._by_frame.get(fid)
        if not obs:
            return None
        tids = [t for t in obs if t in self._points]
        if len(tids) < 12:
            return None
        pts3 = np.asarray([self._points[t] for t in tids], dtype=np.float64)
        pts2 = np.asarray([obs[t] for t in tids], dtype=np.float64)
        zero_dist = np.zeros(5, dtype=np.float64)

        ok, rvec, tvec, inliers = cv2.solvePnPRansac(
            pts3, pts2, self.K, zero_dist,
            reprojectionError=max(3.0, self.max_reproj_px * 2.0),
            confidence=0.9999, iterationsCount=2000, flags=_SQPNP,
        )
        if not ok or inliers is None or len(inliers) < 10:
            return None
        idx = inliers.ravel()
        try:
            rvec, tvec = cv2.solvePnPRefineLM(pts3[idx], pts2[idx], self.K, zero_dist, rvec, tvec)
        except cv2.error:
            pass
        return _View(fid, rvec, tvec)

    def _prune_points(self) -> int:
        """
        Drops bad observations, then landmarks that no longer have enough of them.

        Thresholding a track's *mean* error, as this did, cannot see a track that is
        mostly correct: forty good observations at a pixel each plus two that have
        slid twenty pixels off the feature average under three, so the track is kept
        whole and bundle adjustment can only down-weight the two. Down-weighting is
        not removal, and drift is correlated in time, so what is left is a systematic
        pull on the poses -- which is the error that survives into the depth maps as
        the disagreement floor that sets the finest voxel the mesh can earn. So the
        cut is made per observation, at a multiple of the robust spread of the
        residuals actually present rather than at a fixed pixel count, and a landmark
        is kept only while enough views still see it to triangulate.
        """
        errs_all: List[float] = []
        per_track: Dict[int, List[Tuple[int, float]]] = {}
        for tid, Xw in self._points.items():
            rows: List[Tuple[int, float]] = []
            for f in self._obs[tid]:
                view = self._views.get(f)
                if view is None:
                    continue
                pc = view.R_cw @ Xw + view.tvec
                if pc[2] <= 0.05:
                    rows.append((f, 1e9))
                    continue
                proj = self.K[:2, :2] @ (pc[:2] / pc[2]) + self.K[:2, 2]
                e = float(np.linalg.norm(proj - self._obs[tid][f]))
                rows.append((f, e))
                errs_all.append(e)
            per_track[tid] = rows

        if not errs_all:
            return 0
        finite = np.asarray(errs_all)
        med = float(np.median(finite))
        # Median absolute deviation, scaled to a Gaussian sigma.
        mad = float(np.median(np.abs(finite - med))) * 1.4826
        obs_cut = max(self.max_reproj_px, med + 4.0 * max(mad, 0.15))

        dropped_obs = 0
        dropped = 0
        for tid, rows in per_track.items():
            bad = [f for f, e in rows if e > obs_cut]
            if bad and len(rows) - len(bad) >= self.min_track_len:
                for f in bad:
                    self._obs[tid].pop(f, None)
                    by = self._by_frame.get(f)
                    if by is not None:
                        by.pop(tid, None)
                dropped_obs += len(bad)
                rows = [(f, e) for f, e in rows if e <= obs_cut]
            keep_errs = [e for _, e in rows]
            if len(keep_errs) < 2 or float(np.median(keep_errs)) > self.max_reproj_px * 2.5:
                for f in list(self._obs.get(tid, {})):
                    by = self._by_frame.get(f)
                    if by is not None:
                        by.pop(tid, None)
                del self._points[tid]
                dropped += 1

        if dropped_obs or dropped:
            self.logger.debug(
                f"  SfM pruning: {dropped_obs} observations over {obs_cut:.2f} px "
                f"(median {med:.2f}, sigma {mad:.2f}), {dropped} landmarks retired."
            )
        return dropped

    def _mean_reproj(self) -> float:
        errs: List[float] = []
        for tid, Xw in self._points.items():
            for f, uv in self._obs[tid].items():
                view = self._views.get(f)
                if view is None:
                    continue
                pc = view.R_cw @ Xw + view.tvec
                if pc[2] <= 0.05:
                    continue
                proj = self.K[:2, :2] @ (pc[:2] / pc[2]) + self.K[:2, 2]
                errs.append(float(np.linalg.norm(proj - uv)))
        return float(np.mean(errs)) if errs else float("nan")

    def _bundle_adjust(self, max_nfev: int = 40,
                       window: Optional[int] = None) -> Dict[str, float]:
        """
        Refines registered cameras and landmarks, over a trailing window or globally.

        The first camera is held fixed and a soft baseline anchor pins the scale,
        which removes the 7-dof similarity null space without letting the weakly
        constrained GPS positions bend the relative geometry. Georeferencing is a
        separate similarity fit performed afterwards.

        With ``window`` set, only the most recently registered cameras stay free and
        the older ones are held; their observations of the same landmarks are what
        anchors the window, so no gauge term is needed. This matters because the cost
        of a full solve grows with the whole reconstruction while the newly added
        cameras are the only ones whose estimates actually moved -- re-solving every
        camera each time a dozen frames arrive makes registration slower and slower
        for no gain. Periodic global passes still absorb accumulated drift.
        """
        from scipy.optimize import least_squares
        from scipy.sparse import lil_matrix

        views = sorted(self._views.keys())
        if len(views) < 3 or len(self._points) < 20:
            return {}
        vidx = {f: i for i, f in enumerate(views)}

        if window is not None and len(views) > int(window) + 2:
            free_set = set(views[-int(window):])
        else:
            free_set = set(views[1:])            # camera 0 is the gauge anchor
        free_views = [f for f in views if f in free_set]
        n_free = len(free_views)
        if n_free < 2:
            return {}
        # A window is only worth refining against the structure it can see.
        if len(free_set) < len(views) - 1:
            cand = [t for t, obs in self._obs.items()
                    if t in self._points and not free_set.isdisjoint(obs)]
        else:
            cand = list(self._points.keys())
        if len(cand) < 20:
            return {}

        ranked = sorted(cand, key=lambda t: len(self._obs[t]), reverse=True)
        lm = ranked[:self.max_ba_landmarks]
        lidx = {t: i for i, t in enumerate(lm)}

        # A landmark seen in 350 frames does not constrain the poses 350 times as
        # well as one seen in 20 -- the information saturates once the observations
        # span the available baseline. Long tracks are therefore thinned to an evenly
        # spread subset, which keeps the widest baseline each track offers and keeps
        # the solve affordable now that tracks are replenished instead of frozen at
        # the first frame (11.7k tracks and 1.0M observations, against 3.0k and 0.2M).
        cam_i, pt_i, uvs = [], [], []
        for t in lm:
            obs = [(f, uv) for f, uv in self._obs[t].items() if f in vidx]
            if len(obs) > self.max_obs_per_landmark:
                obs.sort(key=lambda fu: fu[0])
                pick = np.linspace(0, len(obs) - 1, self.max_obs_per_landmark)
                obs = [obs[int(round(i))] for i in pick]
            for f, uv in obs:
                cam_i.append(vidx[f])
                pt_i.append(lidx[t])
                uvs.append(uv)
        if len(uvs) < 100:
            return {}
        cam_i = np.asarray(cam_i, dtype=np.int32)
        pt_i = np.asarray(pt_i, dtype=np.int32)
        uvs = np.asarray(uvs, dtype=np.float64)

        n_cam, n_pt, n_obs = len(views), len(lm), len(uvs)
        base_cams = np.vstack([np.hstack([self._views[f].rvec, self._views[f].tvec])
                               for f in views])
        free_rows = np.asarray([vidx[f] for f in free_views], dtype=np.int64)
        # Scale is only free to drift while a single camera is held; two or more fixed
        # cameras already fix it, and then the anchor term would fight the data.
        use_anchor = (n_cam - n_free) < 2
        n_extra = 1 if use_anchor else 0
        p_pts = np.vstack([self._points[t] for t in lm])
        x0 = np.hstack([base_cams[free_rows].ravel(), p_pts.ravel()])

        anchor_d = float(np.linalg.norm(self._views[views[1]].center -
                                       self._views[views[0]].center))
        anchor_w = 50.0
        fx, fy, cx, cy = self.K[0, 0], self.K[1, 1], self.K[0, 2], self.K[1, 2]

        def unpack(x):
            cams = base_cams.copy()
            cams[free_rows] = x[:6 * n_free].reshape(-1, 6)
            pts = x[6 * n_free:].reshape(-1, 3)
            return cams, pts

        def residuals(x):
            cams, pts = unpack(x)
            Rs = np.empty((n_cam, 3, 3))
            for i in range(n_cam):
                Rs[i] = cv2.Rodrigues(cams[i, :3])[0]
            pc = np.einsum("nij,nj->ni", Rs[cam_i], pts[pt_i]) + cams[cam_i, 3:]
            z = np.where(np.abs(pc[:, 2]) < 1e-6, 1e-6, pc[:, 2])
            u = fx * (pc[:, 0] / z) + cx
            v = fy * (pc[:, 1] / z) + cy
            r = np.empty(2 * n_obs + n_extra)
            r[0:2 * n_obs:2] = u - uvs[:, 0]
            r[1:2 * n_obs:2] = v - uvs[:, 1]
            if use_anchor:
                c1 = -Rs[1].T @ cams[1, 3:]
                c0 = -Rs[0].T @ cams[0, 3:]
                r[-1] = anchor_w * (float(np.linalg.norm(c1 - c0)) - anchor_d)
            return r

        n_par = 6 * n_free + 3 * n_pt
        S = lil_matrix((2 * n_obs + n_extra, n_par), dtype=int)
        rows = np.arange(n_obs)
        col_of_cam = np.full(n_cam, -1, dtype=np.int64)
        col_of_cam[free_rows] = np.arange(n_free)
        fc = col_of_cam[cam_i]
        free_obs = fc >= 0
        for k in range(6):
            cols = fc[free_obs] * 6 + k
            S[2 * rows[free_obs], cols] = 1
            S[2 * rows[free_obs] + 1, cols] = 1
        base = 6 * n_free
        for k in range(3):
            cols = base + pt_i * 3 + k
            S[2 * rows, cols] = 1
            S[2 * rows + 1, cols] = 1
        if use_anchor:
            S[-1, 0:6] = 1

        before = float(np.sqrt(np.mean(residuals(x0)[:2 * n_obs] ** 2)))
        res = least_squares(
            residuals, x0, jac_sparsity=S, verbose=0, x_scale="jac",
            loss="huber", f_scale=max(1.0, self.max_reproj_px),
            method="trf", tr_solver="lsmr", ftol=1e-4, xtol=1e-6, max_nfev=max_nfev,
        )
        after = float(np.sqrt(np.mean(res.fun[:2 * n_obs] ** 2)))

        cams, pts = unpack(res.x)
        for f in free_views:
            i = vidx[f]
            self._views[f] = _View(f, cams[i, :3], cams[i, 3:])
        for i, t in enumerate(lm):
            self._points[t] = pts[i]

        scope = "global" if n_free >= n_cam - 1 else f"window of {n_free}"
        self.logger.info(
            f"Bundle adjustment ({scope}): {n_cam} cameras, {n_pt} landmarks, "
            f"{n_obs} observations, RMS reprojection {before:.2f} -> {after:.2f} px"
        )
        return {"ba_cameras": n_cam, "ba_landmarks": n_pt,
                "ba_rms_before_px": before, "ba_rms_after_px": after}

    @staticmethod
    def _umeyama(src: np.ndarray, dst: np.ndarray, w: Optional[np.ndarray] = None):
        """Weighted similarity fit: dst ~= s * R @ src + t."""
        if w is None:
            w = np.ones(len(src))
        w = w / max(1e-12, w.sum())
        mu_s = (w[:, None] * src).sum(0)
        mu_d = (w[:, None] * dst).sum(0)
        s_c, d_c = src - mu_s, dst - mu_d
        C = (w[:, None] * d_c).T @ s_c
        U, S, Vt = np.linalg.svd(C)
        D = np.eye(3)
        if np.linalg.det(U @ Vt) < 0:
            D[2, 2] = -1.0
        R = U @ D @ Vt
        var_s = float((w[:, None] * s_c ** 2).sum())
        scale = float((S * np.diag(D)).sum() / max(1e-12, var_s))
        t = mu_d - scale * R @ mu_s
        return scale, R, t

    def _align_to_gps(
        self,
        enu: Dict[int, np.ndarray],
        sigma: Optional[Dict[int, float]],
        sigma_up: Optional[Dict[int, float]] = None,
    ):
        """
        Georeferences and metrically scales the reconstruction.

        GPS here is 10 m-class, so a plain least-squares fit would be dragged by
        outliers. Weights are re-derived from the residuals (Huber IRLS) over a few
        passes, which keeps gross GPS jumps from rotating the whole scene.

        Scale is then re-solved with the horizontal and vertical channels weighted by
        their own uncertainties. It matters because the two are rarely comparable: on
        a near-hover ascent the horizontal spread is far smaller than the receiver's
        own error, so an isotropic fit sets metric scale from pure noise, while the
        barometric height it ignores is good to a few centimetres.
        """
        common = [f for f in sorted(self._views) if f in enu]
        if len(common) < 4:
            return None
        src = np.asarray([self._views[f].center for f in common], dtype=np.float64)
        dst = np.asarray([enu[f] for f in common], dtype=np.float64)
        sig = np.asarray([max(0.5, sigma.get(f, 5.0)) if sigma else 5.0 for f in common])
        sig_z = np.asarray(
            [max(0.05, sigma_up.get(f, sig[i])) if sigma_up else sig[i]
             for i, f in enumerate(common)]
        )

        w = 1.0 / sig
        scale, R, t = self._umeyama(src, dst, w)
        for _ in range(6):
            resid = np.linalg.norm((scale * (R @ src.T).T + t) - dst, axis=1)
            med = float(np.median(resid))
            mad = float(np.median(np.abs(resid - med))) * 1.4826
            delta = max(2.0, med + 2.0 * max(mad, 0.5))
            w = (1.0 / sig) * np.where(resid <= delta, 1.0, delta / np.maximum(1e-6, resid))
            scale, R, t = self._umeyama(src, dst, w)

        aniso = self._refit_scale_anisotropic(src, dst, R, w, sig, sig_z)
        if aniso is not None and 0.02 < aniso / max(1e-9, scale) < 50.0:
            mu_s = (w[:, None] * src).sum(0) / max(1e-12, w.sum())
            mu_d = (w[:, None] * dst).sum(0) / max(1e-12, w.sum())
            if abs(aniso - scale) > 0.02 * scale:
                self.logger.info(
                    f"Metric scale re-solved per axis: {scale:.4f} -> {aniso:.4f} "
                    f"(horizontal sigma {float(np.median(sig)):.2f} m, "
                    f"vertical {float(np.median(sig_z)):.2f} m)."
                )
            scale = float(aniso)
            t = mu_d - scale * R @ mu_s

        resid = np.linalg.norm((scale * (R @ src.T).T + t) - dst, axis=1)
        spread = self._scale_observability(src, dst, R, w, sig, sig_z)
        self._apply_similarity(scale, R, t)
        out = {"gps_scale": scale,
               "gps_align_rmse_m": float(np.sqrt(np.mean(resid ** 2))),
               "gps_align_median_m": float(np.median(resid)),
               "gps_align_frames": len(common)}
        if spread is not None:
            out["scale_channel_disagreement"] = spread
        return out

    def _scale_observability(
        self,
        src: np.ndarray,
        dst: np.ndarray,
        R: np.ndarray,
        w: np.ndarray,
        sig: np.ndarray,
        sig_z: np.ndarray,
    ) -> Optional[float]:
        """
        Cross-checks metric scale against the two independent sensor channels.

        Horizontal position and height come from different instruments, so solving
        scale from each and comparing is a ground-truth-free test of whether the
        flight was long enough to fix it at all. Scale is observable only when the
        motion along a channel is large compared with that channel's error, and a
        single pass over a small site may satisfy neither: measured on an 11 s, 2.6 m
        tethered ascent the horizontal channel implied 1.53x and the height channel
        1.00x, and the model came out 1.55x oversized while every reported residual
        looked healthy. The same log needs about 50 m of horizontal travel, or a 10 m
        climb, before the two channels agree to within a few per cent.
        """
        ws = w / max(1e-12, w.sum())
        a = (R @ (src - (ws[:, None] * src).sum(0)).T).T
        b = dst - (ws[:, None] * dst).sum(0)
        per = []
        for axes in ((0, 1), (2,)):
            num = float(sum((a[:, k] * b[:, k]).sum() for k in axes))
            den = float(sum((a[:, k] ** 2).sum() for k in axes))
            per.append(num / den if den > 1e-9 and num > 0.0 else None)
        s_h, s_z = per
        ext_h = float(np.hypot(np.ptp(b[:, 0]), np.ptp(b[:, 1])))
        ext_z = float(np.ptp(b[:, 2]))
        if s_h is None or s_z is None:
            return None
        spread = abs(s_h - s_z) / max(abs(s_h), abs(s_z), 1e-9)
        msg = (
            f"Metric scale cross-check: horizontal channel {s_h:.3f}, height channel "
            f"{s_z:.3f} (they differ by {spread * 100:.0f}%). The flight moved "
            f"{ext_h:.1f} m horizontally against a {float(np.median(sig)):.1f} m fix "
            f"uncertainty and {ext_z:.1f} m vertically against {float(np.median(sig_z)):.2f} m."
        )
        if spread > 0.15:
            self.logger.warning(
                msg + " Absolute scale is not observable from this pass -- distances in "
                "the model may be off by that much. A longer transect, RTK/PPK fixes or "
                "one measured control length would fix it; the shape of the "
                "reconstruction is unaffected."
            )
        else:
            self.logger.info(msg)
        return spread

    @staticmethod
    def _refit_scale_anisotropic(
        src: np.ndarray,
        dst: np.ndarray,
        R: np.ndarray,
        w: np.ndarray,
        sig: np.ndarray,
        sig_z: np.ndarray,
    ) -> Optional[float]:
        """
        Weighted least-squares scale with a separate weight for the vertical axis.

        The rotation is taken from the robust isotropic fit; only the scalar scale is
        re-solved, so a trustworthy height channel can carry it without letting the
        noisy horizontal channel rotate the scene.
        """
        ws = w / max(1e-12, w.sum())
        a = (R @ (src - (ws[:, None] * src).sum(0)).T).T
        b = dst - (ws[:, None] * dst).sum(0)
        # Per-axis precision, scaled by the robust down-weighting already computed.
        prec = np.empty_like(a)
        prec[:, 0] = prec[:, 1] = 1.0 / np.maximum(1e-6, sig ** 2)
        prec[:, 2] = 1.0 / np.maximum(1e-6, sig_z ** 2)
        prec *= (w * sig)[:, None]
        num = float((prec * a * b).sum())
        den = float((prec * a * a).sum())
        if den <= 1e-12 or not np.isfinite(num / den) or num <= 0.0:
            return None
        return num / den

    def _apply_similarity(self, scale: float, R: np.ndarray, t: np.ndarray) -> None:
        """Rigidly rewrites every camera and landmark into the aligned world frame."""
        for f, view in list(self._views.items()):
            R_wc_new = R @ view.R_cw.T
            c_new = scale * (R @ view.center) + t
            rvec = cv2.Rodrigues(R_wc_new.T)[0].reshape(3)
            self._views[f] = _View(f, rvec, -R_wc_new.T @ c_new)
        for tid, X in self._points.items():
            self._points[tid] = scale * (R @ X) + t

    def _flight_axis(self) -> Optional[Tuple[np.ndarray, np.ndarray, float]]:
        """Flight direction, path centroid, and how straight the pass is (0..1)."""
        if len(self._views) < 4:
            return None
        centers = np.asarray([self._views[f].center for f in sorted(self._views)])
        d = centers - centers.mean(0)
        evals, evecs = np.linalg.eigh(np.cov(d.T))
        straightness = float(evals[-1] / max(1e-12, evals.sum()))
        axis = evecs[:, -1]
        axis /= max(1e-12, float(np.linalg.norm(axis)))
        return axis, centers.mean(0), straightness

    def _refit_translation(self, enu: Dict[int, np.ndarray],
                           sigma: Optional[Dict[int, float]],
                           sigma_up: Optional[Dict[int, float]] = None) -> Dict[str, float]:
        """
        Re-centres the scene on GPS with rotation and scale frozen.

        Called after the flight-axis roll is fixed: re-running the full similarity fit
        would discard that correction, because the roll is exactly the direction the
        fit cannot see. Only the translation needs repairing.
        """
        common = [f for f in sorted(self._views) if f in enu]
        if len(common) < 3:
            return {}
        src = np.asarray([self._views[f].center for f in common], dtype=np.float64)
        dst = np.asarray([enu[f] for f in common], dtype=np.float64)
        w = np.asarray([1.0 / max(0.5, sigma.get(f, 5.0)) if sigma else 1.0 for f in common])
        # The height offset is solved with its own weight for the same reason the scale
        # is: a barometric datum locates the model vertically far better than GNSS.
        wz = np.asarray(
            [1.0 / max(0.05, sigma_up.get(f, 1.0 / max(1e-9, w[i]))) if sigma_up else w[i]
             for i, f in enumerate(common)]
        )
        for _ in range(4):
            delta = ((w[:, None] * (dst - src)).sum(0) / max(1e-12, w.sum()))
            delta[2] = float((wz * (dst[:, 2] - src[:, 2])).sum() / max(1e-12, wz.sum()))
            resid = np.linalg.norm(src + delta - dst, axis=1)
            med = float(np.median(resid))
            mad = float(np.median(np.abs(resid - med))) * 1.4826
            lim = max(2.0, med + 2.0 * max(mad, 0.5))
            w = np.where(resid <= lim, w, w * lim / np.maximum(1e-6, resid))
        self._apply_similarity(1.0, np.eye(3), delta)
        resid = np.linalg.norm(src + delta - dst, axis=1)
        return {"gps_align_rmse_m": float(np.sqrt(np.mean(resid ** 2))),
                "gps_align_median_m": float(np.median(resid))}

    def _dominant_plane_normal(self) -> Optional[np.ndarray]:
        """Upward normal of the dominant landmark plane, or None if there isn't one."""
        if len(self._points) < 200:
            return None
        pts = np.asarray(list(self._points.values()), dtype=np.float64)
        try:
            import open3d as o3d
            pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
            span = float(np.linalg.norm(pts.max(0) - pts.min(0)))
            model, inl = pc.segment_plane(distance_threshold=max(0.3, 0.01 * span),
                                          ransac_n=3, num_iterations=600)
        except Exception:
            return None
        if len(inl) < max(100, 0.20 * len(pts)):
            return None
        n = np.asarray(model[:3], dtype=np.float64)
        return n / max(1e-12, float(np.linalg.norm(n)))

    def _resolve_roll(self) -> Dict[str, float]:
        """
        Fixes the one rotation GPS cannot see on a single straight pass.

        Aligning camera centres to GPS leaves rotation about the flight line
        unconstrained, because points on that line barely move under it. The result
        is a scene rolled by an arbitrary angle. That rotation is recovered here from
        scene priors that hold for any downward-looking survey: the dominant surface
        is horizontal, and the scene lies below the camera. Both are exact one-degree-
        of-freedom solves, so nothing is approximated away.
        """
        fa = self._flight_axis()
        if fa is None:
            return {}
        axis, pivot, straightness = fa
        if straightness < 0.90:
            return {}

        def roll_to_align(vec: np.ndarray, target: np.ndarray) -> Optional[float]:
            """Signed angle about `axis` that best rotates `vec` onto `target`."""
            v_p = vec - np.dot(vec, axis) * axis
            t_p = target - np.dot(target, axis) * axis
            if np.linalg.norm(v_p) < 1e-6 or np.linalg.norm(t_p) < 1e-6:
                return None
            v_p /= np.linalg.norm(v_p)
            t_p /= np.linalg.norm(t_p)
            return float(np.arctan2(float(np.dot(np.cross(v_p, t_p), axis)),
                                    float(np.dot(v_p, t_p))))

        up = np.array([0.0, 0.0, 1.0])
        source = "plane"
        theta = None
        n = self._dominant_plane_normal()
        if n is not None:
            theta = roll_to_align(n, up)
        if theta is None:
            # No usable plane: level the mean optical axis instead, which for any
            # aerial pass must point downward.
            source = "optical-axis"
            axes = np.asarray([v.R_cw.T @ np.array([0.0, 0.0, 1.0])
                               for v in self._views.values()])
            mean_axis = axes.mean(0)
            if np.linalg.norm(mean_axis) < 1e-6:
                return {}
            theta = roll_to_align(mean_axis / np.linalg.norm(mean_axis), -up)
        if theta is None:
            return {}

        # Both theta and theta+pi level the plane; only one puts the scene below
        # the cameras, which is the physically possible one.
        best = None
        for cand in (theta, theta + np.pi):
            R = cv2.Rodrigues(axis * cand)[0]
            cams = np.asarray([R @ v.center for v in self._views.values()])
            pts = np.asarray([R @ X for X in self._points.values()])
            drop = float(np.median(cams[:, 2]) - np.median(pts[:, 2]))
            if best is None or drop > best[0]:
                best = (drop, cand, R)
        drop, cand, R = best
        if drop <= 0.0:
            self.logger.warning("Roll disambiguation found no orientation with the scene below the camera.")
        if abs(np.degrees(cand)) < 0.25:
            return {}
        self._apply_similarity(1.0, R, pivot - R @ pivot)
        self.logger.info(
            f"Resolved flight-axis roll: {np.degrees(cand):+.2f} deg from the {source} prior "
            f"(straightness {straightness:.2f}, camera sits {drop:.1f} m above the scene)."
        )
        return {"roll_resolved_deg": float(np.degrees(cand)),
                "roll_prior": 1.0 if source == "plane" else 0.0,
                "path_straightness": straightness}

    def _to_trajectory(self, frame_ids: Sequence[int], stamps: Dict[int, float]) -> Trajectory:
        """
        Builds the trajectory, interpolating any frame SfM could not register so the
        downstream stages still have a pose for every tracking frame.
        """
        traj = Trajectory()
        reg = sorted(self._views.keys())
        for f in reg:
            view = self._views[f]
            traj.add_pose(Pose3D(frame_id=f, timestamp=float(stamps.get(f, 0.0)),
                                 R_wc=view.R_cw.T, t_wc=view.center))
        if not reg:
            return traj

        reg_arr = np.asarray(reg)
        for f in frame_ids:
            f = int(f)
            if f in self._views:
                continue
            j = int(np.searchsorted(reg_arr, f))
            if j == 0 or j >= len(reg_arr):
                near = reg_arr[0] if j == 0 else reg_arr[-1]
                src = traj.poses[int(near)]
                traj.add_pose(Pose3D(frame_id=f, timestamp=float(stamps.get(f, 0.0)),
                                     R_wc=src.R_wc.copy(), t_wc=src.t_wc.copy(),
                                     covariance=np.eye(6) * 0.5))
                continue
            a, b = int(reg_arr[j - 1]), int(reg_arr[j])
            pa, pb = traj.poses[a], traj.poses[b]
            alpha = (f - a) / float(max(1, b - a))
            R = quat_to_rot(quat_slerp(rot_to_quat(pa.R_wc), rot_to_quat(pb.R_wc), alpha))
            traj.add_pose(Pose3D(frame_id=f, timestamp=float(stamps.get(f, 0.0)),
                                 R_wc=R, t_wc=(1 - alpha) * pa.t_wc + alpha * pb.t_wc,
                                 covariance=np.eye(6) * 0.25))
        return traj

    def reconstruct(
        self,
        frame_ids: Sequence[int],
        tracks: Sequence[Track3D],
        telemetry_enu: Optional[Dict[int, np.ndarray]] = None,
        gps_sigma: Optional[Dict[int, float]] = None,
        gps_sigma_up: Optional[Dict[int, float]] = None,
        timestamps: Optional[Dict[int, float]] = None,
    ) -> Tuple[Optional[Trajectory], np.ndarray, Dict[str, Any]]:
        frame_ids = [int(f) for f in frame_ids]
        self._ingest(frame_ids, tracks)
        if len(self._by_frame) < 3:
            self.logger.warning("Incremental SfM: not enough usable tracks.")
            return None, np.empty((0, 3)), {}

        seed = self._seed_pair(frame_ids)
        if seed is None:
            self.logger.warning("Incremental SfM: no well-conditioned seed pair found.")
            return None, np.empty((0, 3)), {}
        f1, f2, inl, R, t = seed

        self._views[f1] = _View(f1, np.zeros(3), np.zeros(3))
        self._views[f2] = _View(f2, cv2.Rodrigues(R)[0].reshape(3), t)
        self._points.update(self._triangulate(inl))
        self.logger.info(
            f"SfM seeded on frames {f1}/{f2} with {len(self._points)} triangulated points."
        )
        if len(self._points) < 30:
            return None, np.empty((0, 3)), {}

        remaining = [f for f in frame_ids if f not in self._views]
        failed: set = set()
        since_ba = 0
        passes = 0
        while remaining:
            scored = []
            for f in remaining:
                obs = self._by_frame.get(f) or {}
                n_seen = sum(1 for t_ in obs if t_ in self._points)
                if n_seen >= 12:
                    scored.append((n_seen, f))
            if not scored:
                break
            scored.sort(reverse=True)
            progressed = False
            for _, f in scored[:8]:
                view = self._resection(f)
                if view is None:
                    failed.add(f)
                    remaining.remove(f)
                    continue
                self._views[f] = view
                remaining.remove(f)
                progressed = True
                since_ba += 1
                new = [t_ for t_ in (self._by_frame.get(f) or {}) if t_ not in self._points]
                if new:
                    self._points.update(self._triangulate(new))
            if not progressed:
                break
            if since_ba >= self.ba_every:
                self._prune_points()
                passes += 1
                if passes % self.global_ba_every == 0:
                    self._bundle_adjust(max_nfev=25)
                else:
                    self._bundle_adjust(max_nfev=15, window=self.ba_window)
                since_ba = 0

        dropped = self._prune_points()
        stats: Dict[str, Any] = {"registered_frames": len(self._views),
                                 "input_frames": len(frame_ids),
                                 "landmarks": len(self._points),
                                 "pruned_landmarks": dropped}
        stats.update(self._bundle_adjust(max_nfev=60))
        stats["mean_reproj_px"] = self._mean_reproj()

        if telemetry_enu:
            gps = self._align_to_gps(telemetry_enu, gps_sigma, gps_sigma_up)
            if gps:
                stats.update(gps)
                roll = self._resolve_roll()
                if roll:
                    stats.update(roll)
                    stats.update(self._refit_translation(telemetry_enu, gps_sigma, gps_sigma_up))
            else:
                self.logger.warning(
                    "Too few GPS-tagged registered frames to georeference; "
                    "the reconstruction stays in its own arbitrary scale."
                )

        stamps = dict(timestamps or {})
        traj = self._to_trajectory(frame_ids, stamps)
        pts = (np.asarray(list(self._points.values()), dtype=np.float64)
               if self._points else np.empty((0, 3)))
        self.logger.info(
            f"Incremental SfM: {len(self._views)}/{len(frame_ids)} frames registered, "
            f"{len(pts)} landmarks, mean reprojection {stats['mean_reproj_px']:.2f} px"
        )
        return traj, pts, stats
