"""
Multi-View Reprojection Quality Verification, Z-Buffer Visibility Testing,
and Normal Consistency Evaluation for SinglePass3D.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import (
    ConfidenceLevel,
    Provenance,
    Trajectory,
    VisibilityState,
    WorldElement,
    WorldElementState,
)
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.video_indexer import VideoIndexer


class MultiViewValidator:
    """
    Independent multi-view cross-validation engine.
    Tests every surface element against all candidate visible camera views.
    """
    def __init__(
        self,
        camera: CameraModel,
        max_reprojection_error_px: float = 3.5,
        normal_consistency_thresh_deg: float = 65.0,
        depth_tolerance_m: float = 0.20
    ):
        self.camera = camera
        self.max_reprojection_error_px = max_reprojection_error_px
        self.normal_consistency_thresh_deg = normal_consistency_thresh_deg
        self.depth_tolerance_m = depth_tolerance_m
        self.logger = get_logger()

    def validate_world(
        self,
        world: PersistentWorld,
        trajectory: Trajectory,
        indexer: VideoIndexer,
        sample_keyframe_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Projects world surfels into candidate views, evaluates photometric consistency,
        view angle vs normal, and updates element reprojection error and visibility.

        Every element is tested against every candidate view, which is a few hundred
        thousand surfels against a few dozen frames -- twenty million tests. Done one
        surfel at a time in Python that is ten minutes of the run, and most of it is
        interpreter overhead: a matrix multiply on a single point, and a rescaled
        camera rebuilt for every pair. The tests are independent, so the loop runs
        per frame over all surfels at once instead, and the camera is scaled once per
        frame. Same tests, same thresholds, same element updates.
        """
        self.logger.info(f"Running Multi-View Reprojection Validation on {len(world.store)} world elements...")

        fids = sample_keyframe_ids or trajectory.frame_ids
        if not fids or len(world.store) == 0:
            return {"mean_reprojection_error": 0.0, "high_confidence_ratio": 1.0}

        all_elements = list(world.store.elements.values())
        live = [e for e in all_elements if e.state != WorldElementState.REJECTED]
        if not live:
            return {"mean_reprojection_error": 0.0, "total_tested": 0, "total_passed": 0}

        cos_normal_thresh = np.cos(np.radians(self.normal_consistency_thresh_deg))
        n_elem = len(live)

        pos = np.ascontiguousarray(
            np.asarray([e.position for e in live], dtype=np.float64).reshape(n_elem, 3)
        )
        nrm = np.ascontiguousarray(
            np.asarray([e.normal for e in live], dtype=np.float64).reshape(n_elem, 3)
        )
        ref_color = np.asarray(
            [int(np.mean(e.color)) for e in live], dtype=np.int32
        )

        # Which (element, frame) pairs are already supporting observations. Frames are
        # mapped to a column index so membership is a lookup rather than a set probe.
        col_of = {int(f): j for j, f in enumerate(fids)}
        supporting = np.zeros((n_elem, len(fids)), dtype=bool)
        for i, e in enumerate(live):
            for f in e.supporting_frames:
                j = col_of.get(int(f))
                if j is not None:
                    supporting[i, j] = True

        # Load grayscale proxy images for candidate views
        view_grays: Dict[int, np.ndarray] = {}
        for fid in fids:
            try:
                img = indexer.get_frame_image(fid, full_resolution=False)
                view_grays[fid] = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            except Exception:
                pass

        total_tests = 0
        total_passed = 0
        err_sum = np.zeros(n_elem, dtype=np.float64)
        err_cnt = np.zeros(n_elem, dtype=np.int64)
        new_views = np.zeros(n_elem, dtype=np.int64)
        added_e: List[np.ndarray] = []
        added_f: List[np.ndarray] = []
        fail_err = float(self.max_reprojection_error_px * 1.5)

        for j, fid in enumerate(fids):
            pose = trajectory.get_pose(fid)
            gray_img = view_grays.get(fid)
            if pose is None or gray_img is None:
                continue

            # 1. Camera frame: X_c = R_cw @ pos + t_cw, for every element at once.
            pt_c = pos @ np.asarray(pose.R_cw, dtype=np.float64).T + np.asarray(
                pose.t_cw, dtype=np.float64
            ).reshape(1, 3)
            keep = pt_c[:, 2] > 0.1  # in front of the camera

            # 2. Normal check: the surface must face the camera, not away from it.
            ray = pos - np.asarray(pose.t_wc, dtype=np.float64).reshape(1, 3)
            ray /= np.maximum(1e-6, np.linalg.norm(ray, axis=1))[:, None]
            keep &= -np.einsum("ij,ij->i", nrm, ray) >= cos_normal_thresh
            cand = np.flatnonzero(keep)
            if cand.size == 0:
                continue

            # 3. Project, with the camera scaled to this view once rather than per element.
            h, w = gray_img.shape
            cam_scaled = self.camera.scale_to_resolution(w, h)
            uv, in_bounds = cam_scaled.project(pt_c[cand])
            cand = cand[np.asarray(in_bounds, dtype=bool)]
            if cand.size == 0:
                continue
            uv = uv[np.asarray(in_bounds, dtype=bool)]
            total_tests += int(cand.size)

            # A frame that already supports an element needs no photometric retest.
            is_sup = supporting[cand, j]
            total_passed += int(is_sup.sum())

            fresh = ~is_sup
            if not fresh.any():
                continue
            ce = cand[fresh]
            u_int = np.rint(uv[fresh, 0]).astype(np.int64)
            v_int = np.rint(uv[fresh, 1]).astype(np.int64)
            inner = (u_int >= 2) & (u_int < w - 2) & (v_int >= 2) & (v_int < h - 2)
            if not inner.any():
                continue
            ce = ce[inner]

            # 4. Photometric consistency against the reference colour.
            diff = np.abs(
                gray_img[v_int[inner], u_int[inner]].astype(np.int32) - ref_color[ce]
            )
            good = diff < 45
            np.add.at(err_sum, ce, np.where(good, diff / 15.0, fail_err))
            np.add.at(err_cnt, ce, 1)
            if good.any():
                ok_e = ce[good]
                total_passed += int(ok_e.size)
                new_views[ok_e] += 1
                added_e.append(ok_e)
                added_f.append(np.full(ok_e.size, int(fid), dtype=np.int64))

        # Fold the newly supporting frames back into the element sets, grouped so each
        # element is touched once instead of once per frame.
        if added_e:
            ae = np.concatenate(added_e)
            af = np.concatenate(added_f)
            order = np.argsort(ae, kind="stable")
            ae, af = ae[order], af[order]
            bounds = np.flatnonzero(np.diff(ae)) + 1
            for chunk in np.split(np.arange(ae.size), bounds):
                if chunk.size:
                    live[ae[chunk[0]]].supporting_frames.update(af[chunk].tolist())

        prior_views = supporting.sum(axis=1)
        n_all = prior_views + new_views
        errors = np.where(err_cnt > 0, err_sum / np.maximum(err_cnt, 1), 1.0)

        for i, e in enumerate(live):
            e.observation_count = int(n_all[i])
            e.reprojection_error = float(errors[i])
            if n_all[i] >= 2:
                e.visibility = VisibilityState.VISIBLE
                if errors[i] < self.max_reprojection_error_px:
                    e.provenance = Provenance.MULTI_VIEW_SUPPORTED
            elif n_all[i] == 1:
                e.visibility = VisibilityState.VISIBLE
                e.provenance = Provenance.OBSERVED
            else:
                e.visibility = VisibilityState.UNKNOWN

        mean_err = float(errors.mean()) if errors.size else 0.0
        self.logger.info(
            f"Multi-View Validation complete. Mean reprojection error: {mean_err:.2f}px. Pass rate: {total_passed}/{max(1, total_tests)} ({total_passed/max(1, total_tests)*100:.1f}%)"
        )
        return {
            "mean_reprojection_error": mean_err,
            "total_tested": total_tests,
            "total_passed": total_passed,
        }
