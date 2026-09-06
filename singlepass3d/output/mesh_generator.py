"""
Surface extraction for SinglePass3D.

Two paths share one finishing pipeline:

* ``generate_mesh_from_depths`` fuses the dense plane-sweep depth maps in a truncated
  signed-distance volume. Every pixel of every depth map contributes, so a roof edge
  measured by forty frames comes out as an edge instead of an average, and free space
  in front of a surface is carved away instead of being filled by an interpolator.
  This is the path that carries fine detail.
* ``generate_mesh`` reconstructs from the sparse verified surfels with screened Poisson.
  It is the fallback for when no dense depth survived, and it can only ever produce the
  smooth, blobby envelope that the surfel cloud supports.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Sequence, Tuple
import cv2
import numpy as np
import trimesh

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import WorldElement, WorldElementState
from singlepass3d.metric_world.persistent_world import PersistentWorld


class MeshGenerator:
    """Builds the final triangle mesh, either volumetrically or from surfels."""

    def __init__(
        self,
        algorithm: str = "tsdf",
        poisson_depth: int = 10,
        min_confidence_to_mesh: float = 0.30,
        tsdf_voxel_m: float = 0.10,
        tsdf_sdf_trunc_mult: float = 4.0,
        smooth_iterations: int = 0,
        depth_trunc_m: float = 150.0,
        ground_align: bool = True,
        complete_surface: bool = True,
        target_mesh_faces: int = 250000,
        include_walls: bool = True,
    ):
        self.algorithm = algorithm.lower()
        self.poisson_depth = int(poisson_depth)
        self.min_confidence_to_mesh = float(min_confidence_to_mesh)
        self.tsdf_voxel_m = float(tsdf_voxel_m)
        self.tsdf_sdf_trunc_mult = float(tsdf_sdf_trunc_mult)
        self.smooth_iterations = int(smooth_iterations)
        self.depth_trunc_m = float(depth_trunc_m)
        self.ground_align = bool(ground_align)
        self.complete_surface = bool(complete_surface)
        self.target_mesh_faces = int(target_mesh_faces) if target_mesh_faces is not None else 250000
        self.include_walls = bool(include_walls)
        # Set when completion runs: the LOD1 wall shell implied by the observed
        # roofs, exported beside the model rather than merged into it.
        self.last_envelope = None
        self.logger = get_logger()
        # Filled in when the model is levelled; maps exported-mesh coordinates back to
        # the reconstruction world frame that the camera poses live in.
        self.mesh_from_world: np.ndarray = np.eye(4)
        self.world_from_mesh: np.ndarray = np.eye(4)

    # ------------------------------------------------------------------ TSDF path

    def generate_mesh_from_depths(
        self,
        depth_frames: Sequence[Any],
        world: Optional[PersistentWorld] = None,
        min_confidence: float = 0.0,
    ) -> Optional[trimesh.Trimesh]:
        """
        Fuses dense per-frame depth maps into a mesh through a TSDF volume.

        `depth_frames` items need `depth` (float32 metres, 0 = invalid), `colors`
        (HxWx3 uint8 RGB), `K`, `mask`, `confidences` and `camera_pose`. Frames are
        integrated one at a time and released, so the disk-backed frames used by the
        pipeline never all sit in memory at once.
        """
        import open3d as o3d

        usable = [f for f in depth_frames if getattr(f, "camera_pose", None) is not None]
        if not usable:
            self.logger.warning("No posed depth maps available for volumetric fusion.")
            return None

        voxel, z_cut, far_voxel = self._plan_fusion(usable)
        # Each band is cleaned before the bands are mixed, because both cleaning
        # rules are voxel-relative and the two bands do not share a voxel. A
        # face-count floor is not comparable across a 2.6x difference in triangle
        # edge length, and a single long-edge limit taken from the preset voxel
        # (0.10 m -> 0.60 m) leaves half-metre triangles stretched across gaps in
        # a band whose real triangles are 7 cm wide -- which is most of what reads
        # as lace in a render of the near field.
        bands = getattr(self, "_bands", None)
        if not bands:
            bands = [(0.0, z_cut, voxel)]
            if far_voxel is not None:
                bands.append((z_cut, float("inf"), far_voxel))
        parts: List[trimesh.Trimesh] = []
        for i, (lo, hi, vx) in enumerate(bands):
            if i == 0:
                label = "near"
            elif np.isfinite(hi):
                label = f"{lo:.0f}-{hi:.0f} m"
            else:
                label = f"beyond {lo:.0f} m"
            band = self._fuse_band(usable, o3d, min_confidence, vx, lo, hi)
            if band is not None:
                parts.append(self._clean_band(band, vx, label))
        parts = [p for p in parts if p is not None and len(p.faces) > 0]
        if not parts:
            self.logger.warning("Every depth map was rejected before fusion.")
            return None
        mesh = parts[0] if len(parts) == 1 else trimesh.util.concatenate(parts)
        mesh = self._drop_islands(mesh, max(b[2] for b in bands))
        mesh = self._close_gaps(mesh, float(bands[0][2]))
        self.logger.info(
            f"Volumetric fusion: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces."
        )
        return self._finalize(mesh, world, dense=True, pre_cleaned=True)

    def _fuse_band(
        self,
        frames: Sequence[Any],
        o3d,
        min_confidence: float,
        voxel: float,
        z_lo: float,
        z_hi: float,
    ) -> Optional[trimesh.Trimesh]:
        """Fuses one depth band into a volume of its own and contours it."""
        trunc = voxel * self.tsdf_sdf_trunc_mult
        volume = o3d.pipelines.integration.ScalableTSDFVolume(
            voxel_length=voxel,
            sdf_trunc=trunc,
            color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8,
        )
        if not np.isfinite(z_hi):
            band = f" beyond {z_lo:.1f} m" if z_lo > 0.0 else ""
        else:
            band = f" out to {z_hi:.1f} m"
        self.logger.info(
            f"Fusing {len(frames)} depth maps{band} at voxel {voxel * 100:.1f} cm "
            f"(SDF truncation {trunc * 100:.1f} cm)."
        )
        integrated = 0
        for frame in frames:
            try:
                rgbd, intr, extr = self._to_rgbd(frame, o3d, min_confidence, z_lo, z_hi)
            except Exception as exc:
                self.logger.debug(f"Skipping frame {getattr(frame, 'frame_id', '?')}: {exc}")
                continue
            if rgbd is None:
                continue
            volume.integrate(rgbd, intr, extr)
            integrated += 1
            release = getattr(frame, "release", None)
            if callable(release):
                release()
        if integrated == 0:
            return None
        mesh_o3d = volume.extract_triangle_mesh()
        mesh_o3d.compute_vertex_normals()
        verts = np.asarray(mesh_o3d.vertices, dtype=np.float64)
        faces = np.asarray(mesh_o3d.triangles, dtype=np.int64)
        if len(faces) == 0:
            return None
        cols = np.asarray(mesh_o3d.vertex_colors, dtype=np.float64)
        vcol = (np.clip(cols, 0.0, 1.0) * 255.0).astype(np.uint8) if len(cols) == len(verts) else None
        self.logger.info(f"  {integrated} frames -> {len(verts)} vertices, {len(faces)} faces.")
        return trimesh.Trimesh(vertices=verts, faces=faces, vertex_colors=vcol, process=False)

    def _plan_fusion(self, frames: Sequence[Any]) -> Tuple[float, float, Optional[float]]:
        """
        Chooses the voxel size, and the range past which a coarser second pass takes over.

        Depth error grows with range. The same disparity uncertainty is worth
        centimetres on a facade a few metres away and decimetres on the terrain at the
        far edge of the frame, and on this data the two nearest views agree to about
        4 cm below 8 m but only to 24 cm past 22 m. One uniform grid cannot serve that
        whole frustum: sized for the near surface it contours the far disagreement into
        permanent relief, which is what shatters a mesh into thousands of detached
        specks, and sized for the far surface it throws away the detail the near
        surface really delivered. So the near band gets the grid it has earned, and
        whatever lies beyond the range where views still agree to within a couple of
        voxels is fused separately at its own scale instead of being discarded.

        Returns the near voxel, the depth where the near band ends, and the far voxel
        (``None`` when everything observed is reliable enough for a single pass).
        """
        z_all, focal = self._depth_samples(frames)
        zs, ds = self._disagreement_samples(frames)
        zr, nr = self._redundancy_samples(frames)
        voxel = self.tsdf_voxel_m
        z_cut = float("inf")
        far_voxel: Optional[float] = None

        def gsd_of(lo: float, hi: float) -> Optional[float]:
            if z_all is None or focal is None or focal <= 1.0:
                return None
            band = z_all[(z_all >= lo) & (z_all < hi)]
            if band.size < 64:
                return None
            return float(np.median(band)) / focal

        def sigma_of(lo: float, hi: float) -> Optional[float]:
            if zs is None:
                return None
            m = (zs >= lo) & (zs < hi)
            if int(m.sum()) < 500:
                return None
            d = ds[m]
            return float(np.median(d[d < np.percentile(d, 85)]))

        def redundancy_of(lo: float, hi: float) -> float:
            if zr is None or nr is None:
                return 1.0
            m = (zr >= lo) & (zr < hi)
            if int(m.sum()) < 500:
                return 1.0
            return float(np.median(nr[m]))

        def size_for(lo: float, hi: float) -> Optional[float]:
            # Two limits apply and the coarser wins. Laterally, a voxel cannot be finer
            # than the spacing of the depth samples that land on the surface: for a
            # single view that is two voxels per resolved sample, which is where the
            # factor of two comes from. But most of this scene is covered from many
            # viewpoints whose pixel grids fall at unrelated offsets, so the fused
            # sample spacing is finer than any one map's and the factor relaxes towards
            # one voxel per sample. Never below one: no amount of redundancy sharpens
            # the lens or the matching window. Along the line of sight, the depth maps
            # only agree with each other to within some distance, and contouring below
            # that turns disagreement into surface relief that is not on the building.
            g, sg = gsd_of(lo, hi), sigma_of(lo, hi)
            if g is None and sg is None:
                return None
            k = 2.0
            if g is not None:
                k = float(np.clip(2.0 / np.sqrt(max(redundancy_of(lo, hi), 1.0)), 1.0, 2.0))
            return float(np.clip(max(k * g if g is not None else 0.0, sg or 0.0), 0.01, 2.0))

        first = size_for(0.0, float("inf"))
        if first is not None:
            voxel = first
        if zs is not None and z_all is not None and zs.size > 5000:
            # Where the near band ends is set by the voxel, and the voxel by the near
            # band, so the two are settled together; a few passes is plenty.
            edges = np.percentile(zs, np.arange(10, 101, 10))
            floor = float(np.percentile(z_all, 55))
            for _ in range(4):
                limit = 2.0 * voxel
                cut = float("inf")
                for lo, hi in zip(np.r_[0.0, edges[:-1]], edges):
                    sg = sigma_of(float(lo), float(hi))
                    if sg is not None and sg > limit:
                        cut = max(float(lo), floor)
                        break
                nxt = size_for(0.0, cut) or voxel
                if abs(nxt - voxel) < 0.02 * voxel and cut == z_cut:
                    z_cut = cut
                    break
                voxel, z_cut = nxt, cut
        if not np.isfinite(z_cut) and zs is not None and z_all is not None and zs.size > 5000:
            # The point-to-plane disagreement above is deliberately blind to the one
            # thing that does grow with range: triangulation precision. Projecting the
            # offset onto the local surface removes the half-pixel lateral artefact, and
            # in doing so it also removes the range dependence that used to end the near
            # band, so nothing stops a 60 m hillside being contoured at a 3 cm grid it
            # cannot possibly support. Depth error from a fixed matching precision grows
            # as the square of range, so the band where views agree to within a couple of
            # voxels ends at z_near * sqrt(2 * voxel / sigma_near) -- focal length and
            # baseline cancel, so this needs no geometry beyond what was just measured.
            z_ref = float(np.median(z_all[z_all > 0.0])) if z_all is not None else 0.0
            s_ref = sigma_of(0.0, z_ref * 1.5) if z_ref > 0.0 else None
            if z_ref > 0.0 and s_ref is not None and s_ref > 1e-4:
                z_lim = z_ref * float(np.sqrt(max(2.0 * voxel, 1e-6) / s_ref))
                if z_lim < float(np.percentile(z_all, 99.0)):
                    # Allow near high-res band to cover full courtyard/background facade depth
                    z_cut = max(z_lim, float(np.percentile(z_all, 75)))
                    voxel = size_for(0.0, z_cut) or voxel
                    self.logger.info(
                        f"Triangulation precision at {z_ref:.1f} m is {s_ref * 100:.1f} cm and "
                        f"grows as range squared, so the near band ends at {z_cut:.1f} m; "
                        f"beyond that a {voxel * 100:.1f} cm grid is finer than the data."
                    )
        if np.isfinite(z_cut):
            beyond = float((z_all >= z_cut).mean()) if z_all is not None else 0.0
            far_voxel = size_for(z_cut, float("inf"))
            if far_voxel is not None:
                far_voxel = float(max(far_voxel, voxel * 1.35))
            if beyond < 0.05 or far_voxel is None:
                far_voxel = None
        if first is not None:
            detail = []
            g0, s0 = gsd_of(0.0, z_cut), sigma_of(0.0, z_cut)
            if g0 is not None:
                n0 = redundancy_of(0.0, z_cut)
                detail.append(f"resolve about {g0 * 100:.1f} cm laterally")
                if zr is not None:
                    k0 = float(np.clip(2.0 / np.sqrt(max(n0, 1.0)), 1.0, 2.0))
                    detail.append(
                        f"cover the near surface from about {n0:.0f} views, which buys "
                        f"{k0:.2f} voxels per sample instead of 2"
                    )
            if s0 is not None:
                detail.append(f"agree to {s0 * 100:.1f} cm in range")
            self.logger.info(
                f"Depth maps {' and '.join(detail) or 'measured'}; TSDF voxel "
                f"{voxel * 100:.1f} cm (preset {self.tsdf_voxel_m * 100:.1f} cm)."
            )
        if far_voxel is not None:
            self.logger.info(
                f"Past {z_cut:.1f} m the views only agree to "
                f"{(sigma_of(z_cut, float('inf')) or 0.0) * 100:.0f} cm; that band is fused "
                f"separately at {far_voxel * 100:.1f} cm rather than contoured as detail."
            )

        centres = np.array(
            [f.camera_pose.t_wc for f in frames if f.camera_pose is not None], dtype=np.float64
        )
        if len(centres) >= 2:
            span = float(np.max(np.ptp(centres, axis=0)))
            # Surfaces observed from a single pass form a band roughly the length of the
            # flight by the swath width; 3x the camera-centre span bounds it generously.
            extent = max(span * 3.0, 20.0)
            needed = max(voxel, extent / 4096.0)
            if needed > voxel * 1.01:
                self.logger.info(
                    f"Scene spans about {extent:.0f} m; relaxing TSDF voxel from "
                    f"{voxel * 100:.1f} cm to {needed * 100:.1f} cm to stay within memory."
                )
                if far_voxel is not None:
                    far_voxel = max(far_voxel, needed * 1.35)
            voxel = float(needed)
        # One far band is not enough. Precision falls off as range squared, so a band
        # that starts at the right voxel is already too fine by a factor of two after
        # only 41% more range -- which is why a single 5 cm band asked to cover 16 m to
        # 100 m contours 30 cm of noise into torn lace instead of surface. Keep going
        # instead: each rung ends where the error has grown to two of its own voxels, at
        # lo * sqrt(2), and the next rung doubles the voxel to match. A handful of rungs
        # covers the whole depth range, and because the shell-area floor in _clean_band
        # is voxel-relative, the coarse rungs discard their own crumbs far more harshly
        # than the fine ones -- exactly the right behaviour that far out.
        bands: List[Tuple[float, float, float]] = [(0.0, float(z_cut), float(voxel))]
        if far_voxel is not None and np.isfinite(z_cut):
            # Cap far field ladder at 45m to prevent noisy sky/horizon ray integration into coarse blocks
            z_top = min(45.0, float(np.percentile(z_all, 98.0)) if z_all is not None else 45.0)
            lo, vx = float(z_cut), float(far_voxel)
            while lo < z_top and len(bands) < 7:
                hi = lo * 1.35
                if vx > 0.35 or hi >= z_top:
                    hi = float("inf")
                bands.append((lo, hi, vx))
                if not np.isfinite(hi):
                    break
                lo, vx = hi, min(vx * 1.5, 0.40)
        self._bands = bands
        if len(bands) > 2:
            ladder = ", ".join(
                f"{lo:.0f}-{hi:.0f} m at {vx * 100:.0f} cm" if np.isfinite(hi)
                else f"beyond {lo:.0f} m at {vx * 100:.0f} cm"
                for lo, hi, vx in bands[1:]
            )
            self.logger.info(
                f"Range precision doubles every {2 ** 0.5:.2f}x of distance, so the far field "
                f"is fused as a ladder rather than one band: {ladder}."
            )
        return float(voxel), float(z_cut), far_voxel

    def _depth_samples(self, frames: Sequence[Any]) -> Tuple[Optional[np.ndarray], Optional[float]]:
        """A subsample of the valid depths across a few frames, and the median focal length."""
        probes = list(frames)[:: max(1, len(frames) // 6)][:6]
        vals: List[np.ndarray] = []
        focals: List[float] = []
        for f in probes:
            try:
                K = np.asarray(f.K, dtype=np.float64)
                d = np.asarray(f.depth, dtype=np.float32)
            except Exception:
                continue
            focal = 0.5 * (float(K[0, 0]) + float(K[1, 1]))
            valid = d[d > 0.0]
            if focal <= 1.0 or valid.size < 64:
                continue
            focals.append(focal)
            vals.append(valid[:: max(1, valid.size // 60000)])
            release = getattr(f, "release", None)
            if callable(release):
                release()
        if not vals:
            return None, None
        return np.concatenate(vals).astype(np.float64), float(np.median(focals))

    def _redundancy_samples(
        self, frames: Sequence[Any]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        How many depth maps see the same surface point, paired with its range.

        A voxel finer than the spacing of the samples that land on a surface contours
        interpolation rather than measurement, and for one depth map that spacing is
        the ground sample distance. This flight, though, covers most surfaces dozens
        of times from viewpoints whose pixel grids fall at unrelated offsets, so the
        fused spacing is finer than any single map's. That is worth measuring rather
        than assuming, because it decides how far the voxel may shrink before holes
        appear. A point counts as covered only where the other map agrees about its
        range, so an occluding surface or a mismatch cannot inflate the count.

        A subset of the depth maps is probed and the count scaled up to the run, which
        is enough: the factor it feeds saturates once four views agree, and the
        question here is only whether a surface is seen once or many times.
        """
        probes = self._probe_depths(frames, 16)
        if len(probes) < 2:
            return None, None
        usable = sum(1 for f in frames if getattr(f, "camera_pose", None) is not None)
        scale = max(1.0, usable / float(len(probes)))
        refs = probes[:: max(1, len(probes) // 4)][:4]
        z_out: List[np.ndarray] = []
        n_out: List[np.ndarray] = []
        for da, Ka, Ra, ta, ia in refs:
            geom = self._reproject_grid(da, Ka)
            if geom is None:
                continue
            pts_a, ok_a = geom
            count = np.zeros(da.shape, dtype=np.float32)
            for db, Kb, Rb, tb, ib in probes:
                if ib == ia:
                    continue
                hit = self._reproject_into(pts_a, ok_a, Ra, ta, db, Kb, Rb, tb)
                if hit is None:
                    continue
                ok, z, sampled = hit[0], hit[1], hit[2]
                # Agreement to within a fiftieth of the range: loose enough that the
                # centimetres two views differ by never costs a count, tight enough
                # that a nearer surface occluding this one cannot supply one.
                count += (ok & (np.abs(z - sampled) < np.maximum(0.05, 0.02 * z))).astype(np.float32)
            m = ok_a & (count > 0.0)
            if int(m.sum()) < 2000:
                continue
            zs = (np.asarray(da, dtype=np.float64))[m]
            stride = max(1, zs.size // 60000)
            z_out.append(zs[::stride])
            n_out.append((count[m][::stride].astype(np.float64) + 1.0) * scale)
        if not z_out:
            return None, None
        return (np.concatenate(z_out).astype(np.float64),
                np.concatenate(n_out).astype(np.float64))

    def _probe_depths(
        self, frames: Sequence[Any], limit: int
    ) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]]:
        """Evenly spaced depth maps with their pose and intrinsics, frames released after."""
        usable = [f for f in frames if getattr(f, "camera_pose", None) is not None]
        if len(usable) < 2:
            return []
        idx = np.unique(np.linspace(0, len(usable) - 1, min(limit, len(usable))).astype(int))
        out: List[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]] = []
        for i in idx:
            f = usable[int(i)]
            try:
                d = np.asarray(f.depth, dtype=np.float32)
                if d.ndim != 2 or d.size < 4096:
                    continue
                out.append((d,
                            np.asarray(f.K, dtype=np.float64),
                            np.asarray(f.camera_pose.R_wc, dtype=np.float64),
                            np.asarray(f.camera_pose.t_wc, dtype=np.float64).reshape(3),
                            int(i)))
            except Exception:
                continue
            finally:
                release = getattr(f, "release", None)
                if callable(release):
                    release()
        return out

    @staticmethod
    def _reproject_grid(
        da: np.ndarray, Ka: np.ndarray
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Back-projects a depth map to camera-local points, with the valid mask."""
        if da.ndim != 2:
            return None
        H, W = da.shape
        u, v = np.meshgrid(np.arange(W, dtype=np.float64), np.arange(H, dtype=np.float64))
        ray = np.stack([(u - Ka[0, 2]) / Ka[0, 0], (v - Ka[1, 2]) / Ka[1, 1], np.ones_like(u)], -1)
        return ray * np.asarray(da, dtype=np.float64)[..., None], da > 0.0

    @staticmethod
    def _reproject_into(
        pts_a: np.ndarray,
        ok_a: np.ndarray,
        Ra: np.ndarray,
        ta: np.ndarray,
        db: np.ndarray,
        Kb: np.ndarray,
        Rb: np.ndarray,
        tb: np.ndarray,
    ) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
        """Carries one camera's points into another view: mask, range, sampled range, pixels."""
        local = (pts_a @ Ra.T + ta - tb) @ Rb
        z = local[..., 2]
        Hb, Wb = db.shape
        with np.errstate(divide="ignore", invalid="ignore"):
            ub = Kb[0, 0] * local[..., 0] / z + Kb[0, 2]
            vb = Kb[1, 1] * local[..., 1] / z + Kb[1, 2]
        ok = ok_a & (z > 0.25) & np.isfinite(ub) & np.isfinite(vb)
        ok &= (ub >= 0) & (ub <= Wb - 1) & (vb >= 0) & (vb <= Hb - 1)
        if int(ok.sum()) < 2000:
            return None
        ub32 = np.where(ok, ub, 0.0).astype(np.float32)
        vb32 = np.where(ok, vb, 0.0).astype(np.float32)
        sampled = cv2.remap(np.asarray(db, dtype=np.float32), ub32, vb32,
                            cv2.INTER_NEAREST, borderValue=0.0)
        ok &= sampled > 0.0
        return ok, z, sampled.astype(np.float64), ub32, vb32, local

    def _disagreement_samples(
        self, frames: Sequence[Any]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        How far apart two depth maps place the same surface, paired with its range.

        This is the number the voxel is sized by along the line of sight, so it has to
        mean the distance between two surfaces and nothing else. Measured the obvious
        way -- reproject a pixel into a neighbour and subtract the two ranges -- it does
        not. The two maps sample the surface on grids that do not line up, so a
        reprojected pixel lands somewhere between its neighbour's samples, and on a
        steep surface that unavoidable half-pixel of lateral offset is centimetres of
        range difference which says nothing about whether the views agree. Charging it
        as error put a floor under the statistic that nothing could lift: it read
        5.8 cm at 960 px and, with a third finer ground sample, 6.5 cm at 1280 px, and
        it moved by hundredths when the poses, the plane budget and the resolution all
        changed underneath it. Since the voxel is the larger of that number and the
        ground sample distance, the whole mesh was being quantised by an artefact of
        how it was measured.

        Projecting the offset onto the neighbour's local surface normal instead asks
        the question the voxel actually depends on: how far is this point from the
        surface the other view reconstructed, rather than how far apart are two samples
        of one slope. Sliding along a plane costs nothing; leaving it costs everything.
        """
        probes = self._probe_depths(frames, 12)
        if len(probes) < 2:
            return None, None
        centres = np.array([p[3] for p in probes], dtype=np.float64)
        z_out: List[np.ndarray] = []
        d_out: List[np.ndarray] = []
        for ai, (da, Ka, Ra, ta, ia) in enumerate(probes):
            # The nearest other camera: the pair whose agreement bounds what any fusion
            # of the two can resolve, and the pair least likely to be looking at
            # different sides of the same wall.
            gap = np.linalg.norm(centres - centres[ai], axis=1)
            gap[ai] = np.inf
            bi = int(np.argmin(gap))
            db, Kb, Rb, tb, _ib = probes[bi]
            geom = self._reproject_grid(da, Ka)
            if geom is None:
                continue
            pts_a, ok_a = geom
            hit = self._reproject_into(pts_a, ok_a, Ra, ta, db, Kb, Rb, tb)
            if hit is None:
                continue
            ok, z, sampled, ub32, vb32, local = hit
            nb, valid = self._local_normals(db, Kb)
            pts_b = (self._reproject_grid(db, Kb) or (None, None))[0]
            if pts_b is None:
                continue
            pts_s = cv2.remap(pts_b.astype(np.float32), ub32, vb32,
                              cv2.INTER_LINEAR, borderValue=0.0)
            nb_s = cv2.remap(nb, ub32, vb32, cv2.INTER_LINEAR, borderValue=0.0)
            # A depth edge interpolates across two surfaces and a collapsed normal
            # carries no plane at all; both are excluded rather than trimmed.
            keep = cv2.remap(valid.astype(np.float32), ub32, vb32,
                             cv2.INTER_NEAREST, borderValue=0.0) > 0.5
            both = ok & keep
            if int(both.sum()) < 2000:
                continue
            n_sel = nb_s[both].astype(np.float64)
            n_sel /= np.maximum(np.linalg.norm(n_sel, axis=-1, keepdims=True), 1e-9)
            delta = local[both] - pts_s[both].astype(np.float64)
            zb = z[both]
            plane = np.abs(np.sum(delta * n_sel, axis=-1))
            # Capped by the plain range difference. Where the normal estimate has gone
            # wrong the projection can exceed it, and a statistic that reports more
            # disagreement than the two ranges actually show would be the old artefact
            # wearing a different hat.
            plane = np.minimum(plane, np.abs(zb - sampled[both]))
            stride = max(1, zb.size // 80000)
            z_out.append(zb[::stride])
            d_out.append(plane[::stride].astype(np.float64))
        if not z_out:
            return None, None
        return (np.concatenate(z_out).astype(np.float64),
                np.concatenate(d_out).astype(np.float64))

    @staticmethod
    def _local_normals(db: np.ndarray, Kb: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Per-pixel surface normal of a depth map in its own camera frame, and validity.

        Fitted to a smoothed copy on purpose. A normal taken straight from the raw map
        tilts to accommodate whatever noise is in the two pixels either side of it, and
        a plane that follows the noise absorbs it: on a synthetic surface carrying 3 cm
        of per-pixel noise the residual against such a plane read 1.2 cm instead of the
        3 cm that was really there. Averaging over a window wider than the noise is
        correlated over -- but far narrower than any real relief -- leaves the normal
        describing the surface, so a noisy sample is charged for its distance from it.
        """
        H, W = db.shape
        u, v = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        ray = np.stack([(u - Kb[0, 2]) / Kb[0, 0], (v - Kb[1, 2]) / Kb[1, 1], np.ones_like(u)], -1)
        d32 = np.asarray(db, dtype=np.float32)
        good = (d32 > 0.0).astype(np.float32)
        k = 7
        # Mask-aware, so the empty pixels a plane-sweep leaves behind do not drag the
        # surface towards the origin, and so a depth edge stays an edge.
        wsum = cv2.boxFilter(good, -1, (k, k), normalize=False)
        dsum = cv2.boxFilter(d32 * good, -1, (k, k), normalize=False)
        enough = wsum >= (k * k) * 0.6
        smooth = np.divide(dsum, wsum, out=np.zeros_like(dsum), where=wsum > 0.0)
        pts = (ray * smooth[..., None]).astype(np.float32)
        gx = cv2.Sobel(pts, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(pts, cv2.CV_32F, 0, 1, ksize=3)
        nb = np.cross(gx, gy)
        nrm = np.linalg.norm(nb, axis=-1, keepdims=True)
        nb = np.divide(nb, nrm, out=np.zeros_like(nb), where=nrm > 1e-12)
        return nb.astype(np.float32), (nrm[..., 0] > 1e-12) & (d32 > 0.0) & enough

    def _to_rgbd(
        self,
        frame: Any,
        o3d,
        min_confidence: float,
        z_lo: float = 0.0,
        z_hi: float = float("inf"),
    ):
        """Turns one cached depth frame into an Open3D RGBD image plus its camera."""
        depth = np.asarray(frame.depth, dtype=np.float32)
        if depth.ndim != 2:
            raise ValueError("depth map is not 2D")
        h, w = depth.shape

        keep = depth > max(0.0, float(z_lo))
        if np.isfinite(z_hi):
            keep &= depth < float(z_hi)
        mask = getattr(frame, "mask", None)
        if mask is not None:
            mask = np.asarray(mask, dtype=bool)
            if mask.shape == depth.shape:
                keep &= mask
        if min_confidence > 0.0:
            conf = getattr(frame, "confidences", None)
            if conf is not None:
                conf = np.asarray(conf, dtype=np.float32)
                if conf.shape == depth.shape:
                    keep &= conf >= min_confidence
        if not np.any(keep):
            return None, None, None

        depth = np.where(keep, depth, 0.0).astype(np.float32)

        colors = np.asarray(frame.colors)
        if colors.ndim == 2:
            colors = np.repeat(colors[..., None], 3, axis=2)
        if colors.dtype != np.uint8:
            colors = np.clip(colors, 0, 255).astype(np.uint8)
        if colors.shape[:2] != depth.shape:
            import cv2
            colors = cv2.resize(colors, (w, h), interpolation=cv2.INTER_AREA)

        K = np.asarray(frame.K, dtype=np.float64)
        intr = o3d.camera.PinholeCameraIntrinsic(
            w, h, float(K[0, 0]), float(K[1, 1]), float(K[0, 2]), float(K[1, 2])
        )
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            o3d.geometry.Image(np.ascontiguousarray(colors)),
            o3d.geometry.Image(np.ascontiguousarray(depth)),
            depth_scale=1.0,
            depth_trunc=self.depth_trunc_m,
            convert_rgb_to_intensity=False,
        )
        # Open3D integrates with the world-to-camera transform.
        return rgbd, intr, np.asarray(frame.camera_pose.T_cw, dtype=np.float64)

    # --------------------------------------------------------------- surfel path

    def generate_mesh(self, world: PersistentWorld) -> trimesh.Trimesh:
        """
        Screened Poisson reconstruction over the verified surfels.

        Used only when volumetric fusion had nothing to work with. The surfel cloud is
        sparse by construction, so this recovers the envelope of the scene, not its detail.
        """
        self.logger.info("Reconstructing surface from persistent world surfels...")

        valid: List[WorldElement] = [
            e for e in world.store.elements.values()
            if e.state != WorldElementState.REJECTED
            and e.confidence_score >= self.min_confidence_to_mesh
        ]
        if len(valid) < 32:
            self.logger.warning(
                f"Only {len(valid)} surfels passed confidence {self.min_confidence_to_mesh}; "
                "the reconstruction has no usable geometry."
            )
            return trimesh.Trimesh(vertices=np.zeros((0, 3)), faces=np.zeros((0, 3), dtype=np.int64))

        pts = np.array([e.position for e in valid], dtype=np.float64)
        normals = np.array([e.normal for e in valid], dtype=np.float64)
        colors = np.array([e.color for e in valid], dtype=np.float64) / 255.0
        normals /= np.maximum(1e-12, np.linalg.norm(normals, axis=1, keepdims=True))

        mesh = None
        try:
            import open3d as o3d
            from scipy.spatial import cKDTree

            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(pts)
            pcd.normals = o3d.utility.Vector3dVector(normals)
            pcd.colors = o3d.utility.Vector3dVector(np.clip(colors, 0.0, 1.0))
            clean, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
            if len(clean.points) >= 32:
                pcd = clean
                pts = np.asarray(pcd.points)
                colors = np.asarray(pcd.colors)

            mesh_o3d, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
                pcd, depth=self.poisson_depth, linear_fit=True
            )
            dens = np.asarray(densities)
            v = np.asarray(mesh_o3d.vertices)
            if len(v) > 0 and len(dens) == len(v):
                tree = cKDTree(pts)
                dist, _ = tree.query(v, k=1)
                # Poisson closes the volume with an outer hull that no measurement
                # supports; drop vertices that sit far from any real surfel.
                reach = max(3.0 * world.voxel_size_m, float(np.quantile(dist, 0.85)))
                mesh_o3d.remove_vertices_by_mask(~((dist <= reach) & (dens >= np.quantile(dens, 0.02))))
                v = np.asarray(mesh_o3d.vertices)
                f = np.asarray(mesh_o3d.triangles)
                if len(v) > 0 and len(f) > 0:
                    _, idx = tree.query(v, k=1)
                    mesh = trimesh.Trimesh(
                        vertices=v, faces=f,
                        vertex_colors=(np.clip(colors[idx], 0.0, 1.0) * 255.0).astype(np.uint8),
                        process=False,
                    )
        except Exception as exc:
            self.logger.warning(f"Poisson reconstruction failed ({exc}); using 2.5D triangulation.")

        if mesh is None or len(mesh.faces) == 0:
            mesh = self._delaunay_25d(pts, colors, world)

        return self._finalize(mesh, world, dense=False)

    def _delaunay_25d(self, pts: np.ndarray, colors: np.ndarray, world: PersistentWorld) -> trimesh.Trimesh:
        """Height-field triangulation: the last resort for aerial-only coverage."""
        from scipy.spatial import Delaunay

        tri = Delaunay(pts[:, :2])
        s = tri.simplices
        edges = np.stack([
            np.linalg.norm(pts[s[:, 0]] - pts[s[:, 1]], axis=1),
            np.linalg.norm(pts[s[:, 1]] - pts[s[:, 2]], axis=1),
            np.linalg.norm(pts[s[:, 2]] - pts[s[:, 0]], axis=1),
        ], axis=1).max(axis=1)
        limit = max(1.0, world.voxel_size_m * 20.0)
        faces = s[edges <= limit]
        if len(faces) == 0:
            faces = s
        return trimesh.Trimesh(
            vertices=pts, faces=faces,
            vertex_colors=(np.clip(colors, 0.0, 1.0) * 255.0).astype(np.uint8),
            process=False,
        )

    # ------------------------------------------------------------------ finishing

    def _finalize(
        self,
        mesh: trimesh.Trimesh,
        world: Optional[PersistentWorld],
        dense: bool,
        pre_cleaned: bool = False,
    ) -> trimesh.Trimesh:
        """
        Removes non-surface artefacts and optionally levels the model on the ground.

        Nothing here smooths by default: the volumetric path already averages many
        measurements per voxel, and a smoothing pass on top of that is exactly what
        turns a roof ridge into a rounded hump.
        """
        if len(mesh.faces) == 0:
            return mesh
        try:
            mesh.update_faces(mesh.nondegenerate_faces())
            if len(mesh.faces) > 0:
                # 1e-10 m2, not 1e-12: this is the threshold the mesh QA gate tests
                # against, and it requires exactly zero faces below it. Culling at
                # 1e-12 here left slivers between the two limits, which is the only
                # reason the mesh gate has never passed on any run of this pipeline.
                mesh.update_faces(mesh.area_faces > 1e-10)
            mesh.remove_unreferenced_vertices()

            if len(mesh.faces) > 0:
                v = mesh.vertices[mesh.faces]
                longest = np.linalg.norm(v - np.roll(v, 1, axis=1), axis=2).max(axis=1)
                if pre_cleaned:
                    limit = None   # already trimmed per band, at each band's voxel
                elif dense:
                    # Marching cubes emits voxel-scale triangles; anything much larger
                    # is a stray shell spanning a gap in the data.
                    limit = self.tsdf_voxel_m * 6.0
                else:
                    limit = max(1.0, float(np.quantile(longest, 0.995)))
                if limit is not None and np.count_nonzero(longest <= limit) >= 32:
                    mesh.update_faces(longest <= limit)
                    mesh.remove_unreferenced_vertices()

            if not pre_cleaned and len(mesh.faces) > 200:
                mesh = self._drop_fragments(mesh)

            if self.smooth_iterations > 0 and len(mesh.vertices) > 100:
                mesh = trimesh.smoothing.filter_taubin(
                    mesh, lamb=0.33, nu=-0.34, iterations=self.smooth_iterations
                )

            if len(mesh.faces) > 200:
                mesh = self._repair_topology(mesh)

            if self.ground_align and len(mesh.vertices) > 100:
                self._align_to_ground(mesh, world)
        except Exception as exc:
            self.logger.debug(f"Mesh finishing step skipped: {exc}")

        # Completion runs last, on the levelled mesh. It needs gravity to be +z to tell
        # a roof from a facade, and it has to happen before texturing so the projection
        # colours the inferred triangles from the same imagery as everything else.
        if self.complete_surface and len(mesh.faces) > 5000:
            from singlepass3d.completion.surface_completion import SurfaceCompleter

            completer = SurfaceCompleter(include_walls=self.include_walls)
            # The implied building envelope is computed from the measured mesh, before
            # the gap fill is folded in, and kept aside for its own artifact.
            self.last_envelope = completer.envelope(mesh)
            mesh = completer.complete(mesh)

        # Quadric Error Decimation simplifies planar surfaces and terrain while preserving
        # sharp building corners and roof ridges. This directly avoids 1-texel/triangle
        # texture degradation during UV atlas synthesis.
        if self.target_mesh_faces > 0 and len(mesh.faces) > self.target_mesh_faces:
            mesh = self._simplify_quadric_decimation(mesh, target_faces=self.target_mesh_faces)
            if len(mesh.faces) > 0:
                mesh.update_faces(mesh.nondegenerate_faces())
                mesh.update_faces(mesh.area_faces > 1e-10)
            mesh.remove_unreferenced_vertices()

        self.logger.info(
            f"Final mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces."
        )
        return mesh

    def _simplify_quadric_decimation(
        self, mesh: trimesh.Trimesh, target_faces: int = 250000
    ) -> trimesh.Trimesh:
        """
        Simplifies dense TSDF volumetric mesh using Quadric Error Decimation.
        Preserves geometric feature edges while reducing triangle density so UV atlas
        cells receive rich multi-texel photographic resolution.
        """
        if len(mesh.faces) <= target_faces:
            return mesh
        try:
            import open3d as o3d

            self.logger.info(
                f"Simplifying mesh via Quadric Decimation: {len(mesh.faces)} -> target {target_faces} faces..."
            )
            mo = o3d.geometry.TriangleMesh(
                o3d.utility.Vector3dVector(np.asarray(mesh.vertices, dtype=np.float64)),
                o3d.utility.Vector3iVector(np.asarray(mesh.faces, dtype=np.int32)),
            )
            if mesh.visual is not None and getattr(mesh.visual, "vertex_colors", None) is not None:
                vc = np.asarray(mesh.visual.vertex_colors)
                if vc.ndim == 2 and len(vc) == len(mesh.vertices):
                    mo.vertex_colors = o3d.utility.Vector3dVector(
                        np.clip(vc[:, :3].astype(np.float64) / 255.0, 0.0, 1.0)
                    )
            simplified_o3d = mo.simplify_quadric_decimation(target_number_of_triangles=target_faces)
            simplified_o3d.remove_degenerate_triangles()
            simplified_o3d.remove_duplicated_triangles()
            simplified_o3d.remove_duplicated_vertices()
            simplified_o3d.remove_non_manifold_edges()
            simplified_o3d.remove_unreferenced_vertices()

            verts = np.asarray(simplified_o3d.vertices)
            faces = np.asarray(simplified_o3d.triangles)
            if len(faces) == 0:
                self.logger.warning("Decimation returned empty faces; keeping original mesh.")
                return mesh

            colors = None
            if simplified_o3d.has_vertex_colors():
                colors = (np.clip(np.asarray(simplified_o3d.vertex_colors), 0.0, 1.0) * 255.0).astype(np.uint8)
                if colors.shape[1] == 3:
                    alpha = np.full((len(colors), 1), 255, dtype=np.uint8)
                    colors = np.hstack([colors, alpha])

            decimated = trimesh.Trimesh(
                vertices=verts,
                faces=faces,
                vertex_colors=colors,
                process=False
            )
            decimated.metadata = dict(mesh.metadata or {})
            self.logger.info(
                f"Quadric decimation complete: {len(decimated.vertices)} vertices, "
                f"{len(decimated.faces)} faces (optimal for high-res UV atlas)."
            )
            return decimated
        except Exception as exc:
            self.logger.warning(f"Quadric decimation skipped ({exc}); retaining mesh.")
            return mesh

    def _repair_topology(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """
        Removes edges shared by three or more faces, so the model can be measured.

        Marching cubes over a TSDF returns a manifold surface, but two independent
        sheets landing within a voxel of each other -- the two faces of a thin wall,
        or a speckle sitting on a roof -- are contoured as one interpenetrating shell,
        and every run of this pipeline has shipped about 7% of its edges in that state
        (22961 of 285443 faces on one, 128924 of 1883578 on another). It is invisible
        in a render and fatal to anything that integrates over the surface: volume,
        area, watertightness, most CAD importers. This is the one QA gate the pipeline
        has never passed.
        """
        import open3d as o3d

        before = len(mesh.faces)
        mo = o3d.geometry.TriangleMesh(
            o3d.utility.Vector3dVector(np.asarray(mesh.vertices, dtype=np.float64)),
            o3d.utility.Vector3iVector(np.asarray(mesh.faces, dtype=np.int32)),
        )
        if mesh.visual is not None and getattr(mesh.visual, "vertex_colors", None) is not None:
            vc = np.asarray(mesh.visual.vertex_colors)
            if vc.ndim == 2 and len(vc) == len(mesh.vertices):
                mo.vertex_colors = o3d.utility.Vector3dVector(
                    np.clip(vc[:, :3].astype(np.float64) / 255.0, 0.0, 1.0)
                )
        mo.remove_duplicated_vertices()
        mo.remove_duplicated_triangles()
        mo.remove_degenerate_triangles()
        mo.remove_non_manifold_edges()
        mo.remove_unreferenced_vertices()
        faces = np.asarray(mo.triangles)
        if faces.size == 0 or len(faces) < before * 0.5:
            # A repair that costs half the model is not a repair; keep the raw surface
            # and let the gate report it rather than silently deleting the result.
            self.logger.warning(
                f"Topology repair would have removed {before - len(faces)} of {before} "
                f"faces; keeping the unrepaired mesh."
            )
            return mesh
        out = trimesh.Trimesh(
            vertices=np.asarray(mo.vertices), faces=faces, process=False
        )
        if mo.has_vertex_colors():
            out.visual.vertex_colors = (
                np.clip(np.asarray(mo.vertex_colors), 0.0, 1.0) * 255.0
            ).astype(np.uint8)
        self.logger.info(
            f"Topology repair: {before - len(faces)} faces removed to clear "
            f"non-manifold edges ({(before - len(faces)) / max(1, before) * 100:.1f}%)."
        )
        return out

    def _clean_band(self, mesh: trimesh.Trimesh, voxel: float, label: str) -> trimesh.Trimesh:
        """
        Trims one depth band using thresholds derived from that band's own voxel.

        Both rules here are voxel-relative, so they have to run before the bands are
        concatenated. The long-edge limit removes triangles marching cubes stretched
        across a hole rather than fitted to a surface; the area floor removes shells
        too small to be a surface at the resolution they were fused at. Area, not
        face count: the far band carries triangles seven times the area of the near
        band's, so counting faces would cull the two bands at wildly different
        physical scales -- and it is the surviving speckle, not the honest voxel
        size, that makes a render look like lace.
        """
        if mesh is None or len(mesh.faces) == 0:
            return mesh
        try:
            mesh.update_faces(mesh.nondegenerate_faces())
            if len(mesh.faces) > 0:
                mesh.update_faces(mesh.area_faces > 1e-10)   # matches the QA gate
            mesh.remove_unreferenced_vertices()
            if len(mesh.faces) == 0:
                return mesh

            v = mesh.vertices[mesh.faces]
            longest = np.linalg.norm(v - np.roll(v, 1, axis=1), axis=2).max(axis=1)
            limit = voxel * 6.0
            keep = longest <= limit
            if int(keep.sum()) >= 32 and not keep.all():
                mesh.update_faces(keep)
                mesh.remove_unreferenced_vertices()

            if len(mesh.faces) > 200:
                # A shell has to be big enough that the imagery could have resolved it
                # as a structure. At a 3 cm voxel the old floor was (18 cm)^2, which let
                # through 17.5% of the mesh as detached crumbs under a third of a square
                # metre -- the lace that makes fine detail read as noise. Real small
                # detail is attached to a larger surface and rides along in its shell.
                floor = max((voxel * 6.0) ** 2, 0.25)
                mesh = self._drop_fragments(mesh, min_area=floor, label=label)
        except Exception as exc:
            self.logger.debug(f"Band cleaning skipped for {label} band: {exc}")
        return mesh

    def _drop_fragments(
        self,
        mesh: trimesh.Trimesh,
        min_area: Optional[float] = None,
        label: str = "",
    ) -> trimesh.Trimesh:
        """
        Keeps the connected surface and discards the speckle of detached shells.

        Clustered through Open3D rather than trimesh.split, which pulls in an optional
        graph dependency that is not installed here and would fail silently.
        """
        import open3d as o3d

        faces = np.asarray(mesh.faces, dtype=np.int32)
        mo = o3d.geometry.TriangleMesh(
            o3d.utility.Vector3dVector(np.asarray(mesh.vertices, dtype=np.float64)),
            o3d.utility.Vector3iVector(faces),
        )
        labels, counts, _ = mo.cluster_connected_triangles()
        labels = np.asarray(labels)
        counts = np.asarray(counts)
        if counts.size <= 1:
            return mesh
        if min_area is not None:
            # Physical area, so the same rule means the same thing in both bands.
            areas = np.bincount(labels, weights=np.asarray(mesh.area_faces),
                                minlength=counts.size)
            alive = areas >= min_area
            if not alive.any():                       # nothing clears the bar
                alive = areas >= float(np.max(areas)) # keep the single best shell
            keep = np.isin(labels, np.nonzero(alive)[0])
            if not keep.any() or keep.all():
                return mesh
            dropped = int(counts.size - alive.sum())
            self.logger.info(
                f"  {label} band: dropped {dropped} shells under "
                f"{min_area:.2f} m2 ({int((~keep).sum())} faces)."
            )
            mesh = mesh.submesh([keep], append=True)
            return mesh
        floor = max(40, int(counts.max() * 0.005))
        keep = np.isin(labels, np.nonzero(counts >= floor)[0])
        if not keep.any() or keep.all():
            return mesh
        self.logger.info(
            f"Discarded {counts.size - int((counts >= floor).sum())} detached fragments "
            f"({int((~keep).sum())} faces)."
        )
        mesh.update_faces(keep)
        mesh.remove_unreferenced_vertices()
        return mesh

    def _close_gaps(self, mesh: trimesh.Trimesh, voxel: float) -> trimesh.Trimesh:
        """
        Closes the pinholes that make a fused facade read as lace rather than surface.

        A boundary loop only a few voxels across is not a real opening: it is a pixel
        the cross-view check happened to reject inside a wall that is otherwise solid.
        Open3D's tensor fill_holes does this well but wants a second copy of the mesh
        and its own index structures, which is more than is free while the fusion
        volumes are still resident -- it failed to allocate on a 2.5 M face mesh here.
        Walking the boundary loops directly costs one pass over the boundary edges and
        nothing else. The size limit is deliberately small, six voxels, so genuine
        openings and the gaps between separate buildings stay open.
        """
        if len(mesh.faces) < 5000:
            return mesh
        try:
            limit = max(6.0 * float(voxel), 0.12)
            faces = np.asarray(mesh.faces, dtype=np.int64)
            verts = np.asarray(mesh.vertices, dtype=np.float64)
            e = np.sort(faces[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
            uniq, cnt = np.unique(e, axis=0, return_counts=True)
            bnd = uniq[cnt == 1]
            if bnd.shape[0] < 3:
                return mesh
            # Adjacency over boundary vertices only. A vertex where three or more
            # boundary edges meet is a pinch point; loops through it are ambiguous, so
            # those are left alone rather than closed the wrong way.
            adj: dict = {}
            for a, b in bnd:
                adj.setdefault(int(a), []).append(int(b))
                adj.setdefault(int(b), []).append(int(a))
            loops: List[List[int]] = []
            seen: set = set()
            for start in adj:
                if start in seen or len(adj[start]) != 2:
                    continue
                loop = [start]
                seen.add(start)
                cur, prev = adj[start][0], start
                while cur not in seen and len(adj.get(cur, ())) == 2:
                    loop.append(cur)
                    seen.add(cur)
                    nxt = adj[cur][0] if adj[cur][0] != prev else adj[cur][1]
                    cur, prev = nxt, cur
                if cur == start and 3 <= len(loop) <= 24:
                    loops.append(loop)
            if not loops:
                return mesh
            add_f: List[np.ndarray] = []
            add_v: List[np.ndarray] = []
            add_src: List[int] = []
            nv = verts.shape[0]
            for loop in loops:
                ring = verts[loop]
                if float(np.linalg.norm(ring.max(axis=0) - ring.min(axis=0))) > limit:
                    continue
                if len(loop) == 3:
                    add_f.append(np.asarray([loop], dtype=np.int64))
                    continue
                c = nv + len(add_v)
                add_v.append(ring.mean(axis=0))
                add_src.append(loop[0])
                idx = np.asarray(loop, dtype=np.int64)
                fan = np.column_stack([idx, np.roll(idx, -1), np.full(idx.size, c)])
                add_f.append(fan)
            if not add_f:
                return mesh
            new_f = np.vstack(add_f)
            if add_v:
                verts = np.vstack([verts, np.asarray(add_v, dtype=np.float64)])
            out = trimesh.Trimesh(verts, np.vstack([faces, new_f]), process=False)
            src = getattr(mesh.visual, "vertex_colors", None)
            if src is not None and len(src) == len(mesh.vertices):
                src = np.asarray(src)
                if add_v:
                    src = np.vstack([src, src[np.asarray(add_src, dtype=np.int64)]])
                out.visual.vertex_colors = src
        except Exception as exc:  # pragma: no cover - geometry is data dependent
            self.logger.debug(f"Gap closing skipped ({exc}).")
            return mesh
        self.logger.info(
            f"Closed {len(loops)} pinholes under {limit * 100:.0f} cm across "
            f"({new_f.shape[0]} triangles) so surfaces read as solid, not lace."
        )
        return out

    def _drop_islands(self, mesh: trimesh.Trimesh, coarsest: float) -> trimesh.Trimesh:
        """
        Intelligent Scene-Aware Geometry Filter:
        1. Anchors all substantial architectural and ground structures (e.g. background buildings,
           courtyards, secondary roofs). Real buildings are never treated as islands.
        2. Specifically detects and purges far-field sky and epipolar ray streaks (deep underground
           or far out in the void beyond the flight corridor).
        3. Culls tiny floating crumbs (< 300 faces, < 0.5 m2) that read as lace.
        4. Retains any medium structures within a generous urban gap tolerance (18-25 m) across
           courtyards and streets.
        """
        import open3d as o3d

        if len(mesh.faces) < 5000:
            return mesh
        try:
            om = o3d.geometry.TriangleMesh(
                o3d.utility.Vector3dVector(np.asarray(mesh.vertices, dtype=np.float64)),
                o3d.utility.Vector3iVector(np.asarray(mesh.faces, dtype=np.int32)),
            )
            lab, cnt, area = om.cluster_connected_triangles()
            lab = np.asarray(lab)
            cnt = np.asarray(cnt)
            area = np.asarray(area)
            if cnt.size < 2:
                return mesh

            verts = np.asarray(mesh.vertices, dtype=np.float64)
            faces = np.asarray(mesh.faces, dtype=np.int32)
            tc = np.asarray(mesh.triangles_center, dtype=np.float64)

            # 1. Establish core scene bounding box from the top components representing >= 70% of faces
            top_indices = np.argsort(cnt)[::-1]
            cum_faces = np.cumsum(cnt[top_indices])
            major_cutoff = np.searchsorted(cum_faces, 0.70 * len(mesh.faces))
            major_comps = top_indices[:max(2, major_cutoff + 1)]

            major_faces = np.isin(lab, major_comps)
            major_v_idx = np.unique(faces[major_faces])
            core_min = verts[major_v_idx].min(axis=0)
            core_max = verts[major_v_idx].max(axis=0)
            core_center = 0.5 * (core_min + core_max)
            core_diag = float(np.linalg.norm(core_max - core_min))

            # 2. Classify clusters: anchors, far-field sky/depth streaks, tiny crumbs
            anchors = []
            drop_mask = np.zeros(cnt.size, dtype=bool)
            dropped_f = 0
            dropped_c = 0
            worst = 0.0

            for i in range(cnt.size):
                sel = np.flatnonzero(lab == i)
                c_verts = verts[np.unique(faces[sel])]
                c_min = c_verts.min(axis=0)
                c_max = c_verts.max(axis=0)
                c_cen = 0.5 * (c_min + c_max)

                # Check if it's underground ray noise, high sky streak, or far-out sparse ray
                is_deep_underground = c_cen[2] < (core_min[2] - 8.0)
                is_high_sky = c_cen[2] > (core_max[2] + 15.0)
                dist_from_core_center = float(np.linalg.norm(c_cen[:2] - core_center[:2]))
                is_far_out = dist_from_core_center > max(35.0, core_diag * 1.2)

                if is_deep_underground or is_high_sky or (is_far_out and cnt[i] < 3000):
                    drop_mask[i] = True
                    dropped_f += int(sel.size)
                    dropped_c += 1
                    worst = max(worst, dist_from_core_center)
                    continue

                # Tiny disconnected crumbs that cause lace
                if cnt[i] < 300 and area[i] < 0.5:
                    drop_mask[i] = True
                    dropped_f += int(sel.size)
                    dropped_c += 1
                    continue

                # Substantial structures are automatically anchored
                if cnt[i] >= 800 or area[i] >= 2.5:
                    anchors.append(i)

            if not anchors:
                anchors = [int(top_indices[0])]

            in_anchors = np.isin(lab, anchors)
            keep = in_anchors.copy()

            # 3. For any remaining unclassified medium components, test proximity to ANY anchored building
            ref = tc[in_anchors]
            step = max(1, ref.shape[0] // 200000)
            tree = o3d.geometry.KDTreeFlann(
                o3d.geometry.PointCloud(o3d.utility.Vector3dVector(ref[::step]))
            )

            # Realistic urban gap tolerance: allows courtyard / street spacing (18-25m)
            urban_gap_limit = max(18.0, 25.0 * float(coarsest))

            for i in range(cnt.size):
                if in_anchors[i] or drop_mask[i]:
                    continue
                sel = np.flatnonzero(lab == i)
                if sel.size == 0:
                    continue
                probe = sel[::max(1, sel.size // 300)]
                d = np.fromiter(
                    (tree.search_knn_vector_3d(tc[j], 1)[2][0] for j in probe),
                    dtype=np.float64,
                    count=probe.size,
                )
                near = float(np.sqrt(np.percentile(d, 5.0)))
                if near <= urban_gap_limit:
                    keep[sel] = True
                else:
                    dropped_f += int(sel.size)
                    dropped_c += 1
                    worst = max(worst, near)

            if dropped_f == 0:
                return mesh

            out = mesh.submesh([np.flatnonzero(keep)], append=True, repair=False)
            self.logger.info(
                f"Intelligent geometry filter: retained {len(anchors)} architectural structures "
                f"({len(out.faces)} faces, kept {len(out.faces)/len(mesh.faces)*100:.1f}%), "
                f"purged {dropped_c} stray sky/debris shells ({dropped_f} faces, furthest {worst:.0f} m out)."
            )
            return out
        except Exception as exc:
            self.logger.warning(f"Geometry filtering skipped ({exc}); retaining mesh.")
            return mesh

    def _align_to_ground(self, mesh: trimesh.Trimesh, world: Optional[PersistentWorld]) -> None:
        """
        Rotates the dominant plane flat, drops it to Z=0 and centres the model in XY.

        The transform is recorded in `world_from_mesh` so anything still expressed in
        the reconstruction's own world frame -- camera poses above all -- can be mapped
        into the exported model's frame instead of silently disagreeing with it.
        """
        import open3d as o3d

        verts = np.asarray(mesh.vertices, dtype=np.float64)
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(verts)
        thresh = max(0.10, self.tsdf_voxel_m * 3.0)
        try:
            plane, inliers = pcd.segment_plane(
                distance_threshold=thresh, ransac_n=3, num_iterations=1000
            )
        except Exception:
            return
        n = np.asarray(plane[:3], dtype=np.float64)
        ln = float(np.linalg.norm(n))
        if ln < 1e-9 or len(inliers) < max(100, 0.05 * len(verts)):
            return
        n /= ln
        if n[2] < 0:
            n = -n
        up = np.array([0.0, 0.0, 1.0])
        if float(np.dot(n, up)) < 0.5:
            # The dominant plane is a wall, not the ground; levelling on it would
            # tip the whole model over.
            R = np.eye(3)
        else:
            axis = np.cross(n, up)
            s, c = float(np.linalg.norm(axis)), float(np.dot(n, up))
            if s < 1e-9:
                R = np.eye(3)
            else:
                vx = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
                R = np.eye(3) + vx + (vx @ vx) * ((1.0 - c) / (s * s))

        rotated = verts @ R.T
        # Ground level from the low tail rather than the single lowest vertex, which is
        # usually a fusion artefact hanging below the terrain.
        z0 = float(np.quantile(rotated[:, 2], 0.01))
        cxy = np.mean(rotated[:, :2], axis=0)
        shift = np.array([-float(cxy[0]), -float(cxy[1]), -z0])

        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = shift
        mesh.apply_transform(T)
        self.mesh_from_world = T
        self.world_from_mesh = np.linalg.inv(T)

        if world is not None:
            for elem in world.store.elements.values():
                elem.position = R @ elem.position + shift
                elem.normal = R @ elem.normal
