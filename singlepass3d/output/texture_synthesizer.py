"""
Multi-view texturing for SinglePass3D.

`synthesize_vertex_colors_projective` is the real path: it samples the rectified source
frames at the exact pixel each mesh vertex projects to, rejects views where the vertex is
back-facing or hidden behind nearer geometry, and blends the surviving samples with a
weighted median so a car driving through the shot cannot smear colour across a facade.

`synthesize_vertex_and_face_colors` remains as a fallback that transfers colour from the
fused surfels; it can never be sharper than the surfel grid.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import Trajectory
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.video_indexer import VideoIndexer


class TextureSynthesizer:
    """Assigns photographic colour to reconstructed geometry."""

    def __init__(self, camera: CameraModel, texture_size: int = 2048):
        self.camera = camera
        self.texture_size = int(texture_size)
        self.logger = get_logger()
        # Fraction of mesh vertices that got colour from a real image sample rather
        # than from hole filling, and how many views contributed. The QA report used
        # to state a hardcoded 98.5% coverage; these are the measured values it needs.
        self.last_direct_coverage: float = 0.0
        self.last_views_used: int = 0
        # Atlas statistics, filled by bake_uv_atlas.
        self.last_atlas_px: int = 0
        self.last_atlas_face_coverage: float = 0.0
        self.last_coverage_funnel: Dict[str, float] = {}
        self.last_atlas_texel_m: float = 0.0

    # ------------------------------------------------------- projective texturing

    def synthesize_vertex_colors_projective(
        self,
        vertices: np.ndarray,
        normals: np.ndarray,
        trajectory: Trajectory,
        indexer: VideoIndexer,
        faces: Optional[np.ndarray] = None,
        max_views_per_vertex: int = 6,
        full_resolution: bool = False,
        world_from_mesh: Optional[np.ndarray] = None,
        max_frames: int = 240,
    ) -> np.ndarray:
        """
        Colours every vertex from the frames that actually saw it.

        `world_from_mesh` maps mesh coordinates back into the frame the camera poses are
        expressed in; the mesh is levelled onto the ground after fusion, so without it
        every projection would be off by that transform.
        """
        V = np.asarray(vertices, dtype=np.float64)
        N = np.asarray(normals, dtype=np.float64)
        n_v = len(V)
        if n_v == 0:
            return np.empty((0, 3), dtype=np.uint8)
        if N.shape != V.shape:
            N = np.zeros_like(V)

        if world_from_mesh is not None:
            T = np.asarray(world_from_mesh, dtype=np.float64)
            V = V @ T[:3, :3].T + T[:3, 3]
            N = N @ T[:3, :3].T
        nn = np.linalg.norm(N, axis=1, keepdims=True)
        N = N / np.maximum(1e-12, nn)

        frame_ids = [fid for fid in sorted(trajectory.poses.keys()) if fid in indexer.frame_index]
        if not frame_ids:
            raise RuntimeError("No trajectory pose has a matching indexed frame.")
        if len(frame_ids) > max_frames:
            sel = np.linspace(0, len(frame_ids) - 1, max_frames).astype(int)
            frame_ids = [frame_ids[i] for i in np.unique(sel)]

        k = max(1, int(max_views_per_vertex))
        samples = np.zeros((n_v, k, 3), dtype=np.float32)
        weights = np.zeros((n_v, k), dtype=np.float32)

        # Which of the three tests loses the surface decides what to do about it, and
        # they call for opposite fixes: a vertex no frame contained is a flight-path
        # limit and nothing here can recover it; one contained but never turned towards
        # a camera is a facade the pass only ever saw edge-on; one that faced a camera
        # and was still rejected was ruled occluded, and that is the only one of the
        # three that could be this code being wrong rather than the data being thin.
        tally = {nm: np.zeros(n_v, dtype=bool) for nm in ("inside", "facing", "visible")}

        cam_scaled: Optional[CameraModel] = None
        used = 0
        for fid in frame_ids:
            pose = trajectory.get_pose(fid)
            if pose is None:
                continue
            try:
                img = indexer.get_frame_image(fid, full_resolution=full_resolution)
            except Exception as exc:
                self.logger.debug(f"Frame {fid} unavailable for texturing: {exc}")
                continue
            h, w = img.shape[:2]
            if cam_scaled is None or cam_scaled.width != w or cam_scaled.height != h:
                cam_scaled = self.camera.scale_to_resolution(w, h)
            self._accumulate_view(V, N, img, pose, cam_scaled, samples, weights, tally)
            used += 1

        colors = self._blend(samples, weights)
        covered = weights[:, 0] > 0
        self.last_direct_coverage = float(covered.mean()) if n_v > 0 else 0.0
        self.last_views_used = int(used)
        self.logger.info(
            f"Projective texturing: {used} views, {covered.mean() * 100:.1f}% of "
            f"{n_v} vertices sampled directly from imagery."
        )
        self.last_coverage_funnel = {
            "in_some_frame": float(tally["inside"].mean()),
            "facing_some_camera": float(tally["facing"].mean()),
            "not_occluded": float(tally["visible"].mean()),
            "sampled": float(covered.mean()),
        }
        self.logger.info(
            f"  coverage: {tally['inside'].mean() * 100:.1f}% fell inside a frame -> "
            f"{tally['facing'].mean() * 100:.1f}% turned towards it -> "
            f"{tally['visible'].mean() * 100:.1f}% not occluded by nearer surface."
        )
        if not covered.all():
            colors = self._fill_gaps(V, colors, covered, faces)
        return np.clip(colors, 0, 255).astype(np.uint8)

    def _accumulate_view(
        self,
        V: np.ndarray,
        N: np.ndarray,
        img: np.ndarray,
        pose,
        cam: CameraModel,
        samples: np.ndarray,
        weights: np.ndarray,
        tally: Optional[Dict[str, np.ndarray]] = None,
    ) -> None:
        """Projects every vertex into one frame and records the colour where it is visible."""
        h, w = img.shape[:2]
        pc = (V - pose.t_wc) @ pose.R_cw.T
        z = pc[:, 2]
        ahead = z > 0.2
        if not np.any(ahead):
            return

        safe = np.where(ahead, z, 1.0)
        u = cam.fx * (pc[:, 0] / safe) + cam.cx
        v = cam.fy * (pc[:, 1] / safe) + cam.cy
        inside = ahead & (u >= 1) & (u <= w - 2) & (v >= 1) & (v <= h - 2)
        if tally is not None:
            tally["inside"] |= inside
        if not np.any(inside):
            return

        # Only surfaces turned towards the camera may contribute.
        ray = pc / np.maximum(1e-12, np.linalg.norm(pc, axis=1, keepdims=True))
        n_cam = N @ pose.R_cw.T
        facing = -np.sum(n_cam * ray, axis=1)
        cand = inside & (facing > 0.15)
        if tally is not None:
            tally["facing"] |= cand
        if not np.any(cand):
            return

        idx = np.nonzero(cand)[0]
        vis = self._visible(u[idx], v[idx], z[idx], w, h)
        idx = idx[vis]
        if tally is not None:
            tally["visible"][idx] = True
        if idx.size == 0:
            return

        cols = self._sample(img, u[idx], v[idx])
        # Sharpness of the frame, resolution at that distance, and how square-on the
        # surface is: the three things that decide whether a sample is worth keeping.
        sharp = self._sharpness(img)
        wgt = (facing[idx] ** 2) * sharp / np.maximum(1.0, z[idx] ** 2)
        wgt = wgt.astype(np.float32)

        # Keep the k strongest views per vertex without storing every observation.
        slot = np.argmin(weights[idx], axis=1)
        rows = np.arange(idx.size)
        better = wgt > weights[idx, slot]
        if not np.any(better):
            return
        tgt = idx[better]
        sl = slot[better]
        samples[tgt, sl] = cols[rows[better]]
        weights[tgt, sl] = wgt[better]

    def _visible(self, u: np.ndarray, v: np.ndarray, z: np.ndarray, w: int, h: int) -> np.ndarray:
        """
        Splat depth buffer: a vertex is hidden when a nearer vertex claimed its pixel.

        The mesh is denser than the image at texturing resolution, so splatting the
        vertices themselves resolves occlusion without a rasteriser; the tolerance keeps
        a surface from occluding itself across the depth quantisation of one pixel.
        """
        zbuf = np.full((h, w), np.inf, dtype=np.float32)
        pu = np.clip(u.astype(np.int32), 0, w - 1)
        pv = np.clip(v.astype(np.int32), 0, h - 1)
        flat = pv.astype(np.int64) * w + pu
        np.minimum.at(zbuf.reshape(-1), flat, z.astype(np.float32))
        tol = np.maximum(0.30, 0.03 * z)
        return z <= zbuf.reshape(-1)[flat] + tol

    @staticmethod
    def _sample(img: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """
        Bilinear colour lookup at sub-pixel positions.

        Sampled in blocks: cv2.remap stores map dimensions in a short, so a single
        1xN map silently breaks the moment the mesh passes 32767 vertices.
        """
        n = int(u.size)
        out = np.empty((n, 3), dtype=np.float32)
        step = 16384
        uf = u.astype(np.float32)
        vf = v.astype(np.float32)
        for a in range(0, n, step):
            b = min(n, a + step)
            block = cv2.remap(
                img, uf[a:b].reshape(1, -1), vf[a:b].reshape(1, -1),
                cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT,
            )
            out[a:b] = block.reshape(-1, 3).astype(np.float32)
        return out

    def _sharpness(self, img: np.ndarray) -> float:
        """Relative focus measure; motion-blurred frames lose out to sharp ones."""
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        if max(g.shape) > 512:
            f = 512.0 / max(g.shape)
            g = cv2.resize(g, (int(g.shape[1] * f), int(g.shape[0] * f)), interpolation=cv2.INTER_AREA)
        var = float(cv2.Laplacian(g, cv2.CV_32F).var())
        return float(np.clip(var / 100.0, 0.05, 10.0))

    def _blend(self, samples: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """
        Weighted median first, then a weighted mean of the samples that agree with it.

        The median decides which observations are the outliers -- a pedestrian, a
        specular highlight, one badly exposed frame -- and the restricted mean then
        recovers the noise reduction that averaging gives without their influence.
        """
        n = samples.shape[0]
        out = np.full((n, 3), 150.0, dtype=np.float32)
        total = weights.sum(axis=1)
        have = total > 0
        if not np.any(have):
            return out

        rows = np.nonzero(have)[0]
        s = samples[rows]
        w = weights[rows]
        t = total[rows]
        med = np.empty((len(rows), 3), dtype=np.float32)
        ar = np.arange(len(rows))
        for c in range(3):
            order = np.argsort(s[:, :, c], axis=1)
            sv = np.take_along_axis(s[:, :, c], order, axis=1)
            sw = np.take_along_axis(w, order, axis=1)
            pick = np.argmax(np.cumsum(sw, axis=1) >= 0.5 * t[:, None], axis=1)
            med[:, c] = sv[ar, pick]

        lum = s.mean(axis=2)
        lum_med = med.mean(axis=1)[:, None]
        agree = (np.abs(lum - lum_med) <= 40.0) & (w > 0)
        wa = np.where(agree, w, 0.0)
        denom = wa.sum(axis=1)
        ok = denom > 0
        blended = np.where(
            ok[:, None],
            np.einsum("nk,nkc->nc", wa, s) / np.maximum(1e-6, denom)[:, None],
            med,
        )
        out[rows] = blended.astype(np.float32)
        return out

    def _fill_gaps(
        self,
        V: np.ndarray,
        colors: np.ndarray,
        covered: np.ndarray,
        faces: Optional[np.ndarray],
    ) -> np.ndarray:
        """
        Gives unseen vertices the colour of the nearest surfaces that were seen.

        Occluded pockets and the underside of overhangs are never observed from the air;
        leaving them grey reads as a hole in the model, so they inherit their surroundings.
        """
        from scipy.spatial import cKDTree

        if not np.any(covered):
            return colors
        tree = cKDTree(V[covered])
        src = colors[covered]
        k = min(4, int(covered.sum()))
        dist, idx = tree.query(V[~covered], k=k, workers=-1)
        if k == 1:
            dist = dist.reshape(-1, 1)
            idx = idx.reshape(-1, 1)
        wgt = 1.0 / np.maximum(1e-3, dist)
        wgt /= wgt.sum(axis=1, keepdims=True)
        colors[~covered] = np.einsum("nk,nkc->nc", wgt, src[idx]).astype(np.float32)
        self.logger.info(
            f"Filled {int((~covered).sum())} unobserved vertices from neighbouring colour."
        )
        return colors

    # ---------------------------------------------------------- surfel fallback

    def synthesize_vertex_and_face_colors(
        self,
        vertices: np.ndarray,
        normals: np.ndarray,
        world: PersistentWorld,
        trajectory: Trajectory,
        indexer: VideoIndexer,
    ) -> np.ndarray:
        """
        Transfers colour from the fused surfels by inverse-distance interpolation.

        Only used when projective texturing could not run; resolution is capped by the
        surfel spacing, so edges come out soft.
        """
        V = np.asarray(vertices, dtype=np.float64)
        if len(V) == 0:
            return np.empty((0, 3), dtype=np.uint8)

        from scipy.spatial import cKDTree
        from singlepass3d.core.types import WorldElementState

        elements = [e for e in world.store.elements.values() if e.state != WorldElementState.REJECTED]
        if not elements:
            self.logger.warning("No surfels available for colour transfer; mesh stays untextured.")
            return np.full((len(V), 3), 150, dtype=np.uint8)

        pts = np.array([e.position for e in elements], dtype=np.float64)
        cols = np.array([e.color for e in elements], dtype=np.float64)
        tree = cKDTree(pts)
        k = min(3, len(pts))
        dist, idx = tree.query(V, k=k, workers=-1)
        if k == 1:
            dist = dist.reshape(-1, 1)
            idx = idx.reshape(-1, 1)
        wgt = 1.0 / np.maximum(1e-4, dist)
        wgt /= wgt.sum(axis=1, keepdims=True)
        out = np.einsum("nk,nkc->nc", wgt, cols[idx])
        self.logger.info(f"Transferred surfel colour to {len(V)} vertices.")
        return np.clip(out, 0, 255).astype(np.uint8)

    # ------------------------------------------------------------------ UV atlas

    def bake_uv_atlas(
        self,
        mesh: Any,
        trajectory: Trajectory,
        indexer: VideoIndexer,
        world_from_mesh: Optional[np.ndarray] = None,
        full_resolution: bool = True,
        max_frames: int = 240,
        max_atlas_px: int = 8192,
        top_views: int = 2,
    ) -> Optional[Any]:
        """
        Bakes a real UV atlas: one texel grid per triangle, sampled from the imagery.

        Colour on the vertices is capped by the fusion voxel, one sample every few
        centimetres of surface however sharp the frames are, and that cap is most of
        what makes a correct model look blurred. The frames resolve the facade several
        times finer than the voxel and all of it was being discarded at export:
        `texture.png` was a palette dump and the exported OBJ carried nothing a
        renderer could map. Here every triangle gets its own square cell in an atlas,
        sized so one texel lands near the ground sample distance of the frames, and
        every texel is projected into the two frames that see that triangle best and
        sampled there. Triangles no frame saw keep the colour their corners already
        carry, so the atlas has no holes.

        Returns a new mesh with unwelded vertices and per-corner UVs -- an atlas needs
        a seam at every triangle, so corners cannot be shared -- or ``None`` when
        there is nothing to bake.
        """
        try:
            import trimesh
            from PIL import Image
        except Exception as exc:
            self.logger.warning(f"UV atlas needs trimesh and PIL ({exc}); keeping vertex colour.")
            return None
        V = np.asarray(mesh.vertices, dtype=np.float64)
        F = np.asarray(mesh.faces, dtype=np.int64)
        n_f = int(len(F))
        if n_f == 0 or len(V) == 0:
            return None
        Vw = V
        if world_from_mesh is not None:
            T = np.asarray(world_from_mesh, dtype=np.float64)
            Vw = V @ T[:3, :3].T + T[:3, 3]
        P = Vw[F]
        e1 = P[:, 1] - P[:, 0]
        e2 = P[:, 2] - P[:, 0]
        fn = np.cross(e1, e2)
        area2 = np.linalg.norm(fn, axis=1)
        fn = fn / np.maximum(1e-12, area2[:, None])
        cen = P.mean(axis=1)
        edge = float(np.median(np.sqrt(np.maximum(area2, 1e-12))))

        frame_ids = [fid for fid in sorted(trajectory.poses.keys()) if fid in indexer.frame_index]
        if not frame_ids:
            return None
        if len(frame_ids) > max_frames:
            sel = np.unique(np.linspace(0, len(frame_ids) - 1, max_frames).astype(int))
            frame_ids = [frame_ids[int(i)] for i in sel]
        try:
            probe = indexer.get_frame_image(frame_ids[0], full_resolution=full_resolution)
        except Exception as exc:
            self.logger.warning(f"UV atlas cannot read imagery ({exc}); keeping vertex colour.")
            return None
        cam_ref = self.camera.scale_to_resolution(probe.shape[1], probe.shape[0])
        centres = np.array([trajectory.get_pose(f).t_wc for f in frame_ids
                            if trajectory.get_pose(f) is not None], dtype=np.float64)
        if len(centres) == 0:
            return None
        sub = cen[:: max(1, n_f // 20000)]
        z_med = float(np.median(np.linalg.norm(sub[:, None, :] - centres[None, :, :],
                                              axis=2).min(axis=1)))
        # One texel per ground sample of the imagery: finer invents detail, coarser
        # throws away what the frames already resolved.
        gsd = max(1e-4, z_med / max(1.0, float(cam_ref.fx)))
        max_cell = 16 if max_atlas_px >= 4096 else 8
        cell = int(np.clip(round(edge / gsd), 2, max_cell))
        grid = int(np.ceil(np.sqrt(n_f)))
        # A finer mesh is worth more than a finer texture once the triangles are already
        # smaller than the ground sample of the imagery, which is where this fusion now
        # lands: at a 3 cm voxel against 2.4 cm frames, two texels across a triangle is
        # oversampling and one is exactly the imagery's own resolution. So the cell
        # shrinks to one rather than the atlas being abandoned -- which is what used to
        # happen past roughly four million triangles, silently reverting the whole model
        # to a vertex palette at voxel spacing, the coarsest appearance the pipeline can
        # produce, precisely when the geometry had come out best.
        pad = 2
        while cell > 1 and grid * (cell + pad) > max_atlas_px:
            cell -= 1
        if grid * (cell + pad) > max_atlas_px:
            # Two texels of gutter around a one texel cell is 200% overhead, and it is
            # what pushes a ten million triangle mesh over the atlas limit. One texel is
            # enough: every UV lands exactly on a cell centre, so bilinear sampling only
            # reaches the gutter at the very edge of a triangle, and the dilation below
            # fills the gutter with the neighbouring cell's own colour before export.
            pad = 1
        if grid * (cell + pad) > max_atlas_px:
            self.logger.info(
                f"{n_f} triangles need more than {max_atlas_px} px of atlas at a single "
                f"texel each; keeping vertex colour."
            )
            return None
        stride = cell + pad
        side = grid * stride

        ix, iy = np.meshgrid(np.arange(cell), np.arange(cell))
        keep = (ix + iy) <= cell
        ix, iy = ix[keep].astype(np.int32), iy[keep].astype(np.int32)
        ta = (ix + 0.5) / float(cell)
        tb = (iy + 0.5) / float(cell)
        over = np.maximum(1.0, ta + tb)
        ta, tb = ta / over, tb / over
        t_n = int(ta.size)
        cellx = (np.arange(n_f) % grid).astype(np.float64) * stride + 1.0
        celly = (np.arange(n_f) // grid).astype(np.float64) * stride + 1.0

        k = max(1, int(top_views))
        best_w = np.zeros((n_f, k), dtype=np.float32)
        best_v = np.full((n_f, k), -1, dtype=np.int32)
        for j, fid in enumerate(frame_ids):
            pose = trajectory.get_pose(fid)
            if pose is None:
                continue
            try:
                img = indexer.get_frame_image(fid, full_resolution=full_resolution)
            except Exception:
                continue
            h, w = img.shape[:2]
            cam = self.camera.scale_to_resolution(w, h)
            pc = (cen - pose.t_wc) @ pose.R_cw.T
            z = pc[:, 2]
            ahead = z > 0.2
            if not np.any(ahead):
                continue
            safe = np.where(ahead, z, 1.0)
            u = cam.fx * (pc[:, 0] / safe) + cam.cx
            v = cam.fy * (pc[:, 1] / safe) + cam.cy
            cand = ahead & (u >= 1) & (u <= w - 2) & (v >= 1) & (v <= h - 2)
            ray = pc / np.maximum(1e-12, np.linalg.norm(pc, axis=1, keepdims=True))
            facing = -np.sum((fn @ pose.R_cw.T) * ray, axis=1)
            cand &= facing > 0.15
            if not np.any(cand):
                continue
            idx = np.nonzero(cand)[0]
            idx = idx[self._visible(u[idx], v[idx], z[idx], w, h)]
            if idx.size == 0:
                continue
            wgt = ((facing[idx] ** 2) * self._sharpness(img)
                   / np.maximum(1.0, z[idx] ** 2)).astype(np.float32)
            slot = np.argmin(best_w[idx], axis=1)
            better = wgt > best_w[idx, slot]
            if not np.any(better):
                continue
            best_w[idx[better], slot[better]] = wgt[better]
            best_v[idx[better], slot[better]] = j

        acc = np.zeros((n_f * t_n, 3), dtype=np.float32)
        wac = np.zeros(n_f * t_n, dtype=np.float32)
        offs = np.arange(t_n, dtype=np.int64)
        for j, fid in enumerate(frame_ids):
            hit = np.nonzero(np.any(best_v == j, axis=1))[0]
            if hit.size == 0:
                continue
            pose = trajectory.get_pose(fid)
            try:
                img = indexer.get_frame_image(fid, full_resolution=full_resolution)
            except Exception:
                continue
            h, w = img.shape[:2]
            cam = self.camera.scale_to_resolution(w, h)
            wj = np.where(best_v[hit] == j, best_w[hit], 0.0).max(axis=1).astype(np.float32)
            for s0 in range(0, hit.size, 30000):
                blk = hit[s0:s0 + 30000]
                pts = (P[blk, 0][:, None, :]
                       + ta[None, :, None] * e1[blk][:, None, :]
                       + tb[None, :, None] * e2[blk][:, None, :]).reshape(-1, 3)
                pc = (pts - pose.t_wc) @ pose.R_cw.T
                zz = np.maximum(pc[:, 2], 1e-6)
                uu = np.clip(cam.fx * (pc[:, 0] / zz) + cam.cx, 0.0, w - 1.0)
                vv = np.clip(cam.fy * (pc[:, 1] / zz) + cam.cy, 0.0, h - 1.0)
                cols = self._sample(img, uu, vv)
                ww = np.repeat(wj[s0:s0 + blk.size], t_n)
                flat = (blk[:, None] * t_n + offs[None, :]).reshape(-1)
                acc[flat] += cols * ww[:, None]
                wac[flat] += ww

        good = wac > 0.0
        vals = np.zeros((n_f * t_n, 3), dtype=np.float32)
        vals[good] = acc[good] / wac[good][:, None]
        vcol = None
        try:
            vc = np.asarray(mesh.visual.vertex_colors)
            if vc is not None and len(vc) == len(V):
                vcol = vc[:, :3].astype(np.float32)
        except Exception:
            vcol = None
        if vcol is not None and not np.all(good):
            miss = np.nonzero(~good)[0]
            fi, ti = miss // t_n, miss % t_n
            aa, bb = ta[ti][:, None], tb[ti][:, None]
            vals[miss] = (vcol[F[fi, 0]] * (1.0 - aa - bb)
                          + vcol[F[fi, 1]] * aa + vcol[F[fi, 2]] * bb)
        atlas = np.zeros((side, side, 3), dtype=np.uint8)
        painted = np.zeros((side, side), dtype=bool)
        tx = (cellx[:, None] + ix[None, :]).astype(np.int32).reshape(-1)
        ty = (celly[:, None] + iy[None, :]).astype(np.int32).reshape(-1)
        atlas[ty, tx] = np.clip(vals, 0.0, 255.0).astype(np.uint8)
        painted[ty, tx] = True
        if not painted.all():
            # A one texel gutter around every cell, so bilinear sampling at a triangle
            # edge cannot pull the background in.
            grown = cv2.dilate(atlas, np.ones((3, 3), np.uint8))
            atlas = np.where(np.repeat((~painted)[:, :, None], 3, axis=2), grown, atlas)
        corners = np.empty((n_f, 3, 2), dtype=np.float64)
        corners[:, 0, 0], corners[:, 0, 1] = cellx, celly
        corners[:, 1, 0], corners[:, 1, 1] = cellx + cell, celly
        corners[:, 2, 0], corners[:, 2, 1] = cellx, celly + cell
        uv = corners.reshape(-1, 2) / float(side)
        uv[:, 1] = 1.0 - uv[:, 1]
        out = trimesh.Trimesh(vertices=V[F].reshape(-1, 3),
                              faces=np.arange(n_f * 3, dtype=np.int64).reshape(n_f, 3),
                              process=False)
        out.visual = trimesh.visual.TextureVisuals(uv=uv, image=Image.fromarray(atlas))
        self.last_atlas_px = int(side)
        self.last_atlas_face_coverage = float(np.mean(best_v[:, 0] >= 0))
        self.last_atlas_texel_m = float(edge / cell)
        self.logger.info(
            f"UV atlas: {side}x{side} px, {cell} texels across each of {n_f} triangles, "
            f"{self.last_atlas_texel_m * 100:.1f} cm per texel against {gsd * 100:.1f} cm "
            f"of imagery; {self.last_atlas_face_coverage * 100:.1f}% of triangles sampled "
            f"from a frame that saw them."
        )
        return out

    def generate_texture_image(self, colors_uint8: np.ndarray, output_path: str | Path) -> np.ndarray:
        """
        Writes the vertex palette as an image for inspection.

        This is a diagnostic dump, not a UV atlas: colour lives on the vertices of the
        exported mesh, and a real atlas would need a UV unwrap that this build has no
        packer for. Sized to the sample count so nothing is invented by resampling.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        n = len(colors_uint8)
        if n == 0:
            img = np.full((16, 16, 3), 150, dtype=np.uint8)
        else:
            side = int(np.ceil(np.sqrt(n)))
            flat = np.full((side * side, 3), 150, dtype=np.uint8)
            flat[:n] = np.asarray(colors_uint8, dtype=np.uint8).reshape(-1, 3)
            img = flat.reshape(side, side, 3)
        cv2.imwrite(str(out), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        return img
