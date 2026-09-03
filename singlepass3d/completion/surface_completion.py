"""
Geometry-constrained completion of the fused surface.

The pipeline already had a completion stage, but it worked on the persistent-world
surfel store while the delivered mesh is contoured straight from the depth maps, so
its inferred elements never reached an artifact: 3.5 minutes per run for 500 surfels
that no exported file contains. This module completes the mesh itself, and only where
the observed geometry decides the answer rather than a prior:

  * a hole fully enclosed by observed surface on a detected plane is interpolation,
    so it is filled at the plane;
  * a roof observed from above with nothing under its rim implies walls, because a
    roof does not float -- so the rim is extruded straight down until it meets
    observed surface, or the ground the mesh is already levelled on.

Nothing here invents a facade nobody saw, adds detail, or extends a silhouette
outward. Every triangle it adds is tagged, counted and reported as inferred, so a
measurement never mistakes it for evidence.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import trimesh

from singlepass3d.core.logging import get_logger


class SurfaceCompleter:
    """Fills enclosed planar holes and extrudes walls under observed roofs."""

    def __init__(
        self,
        cell_m: float = 0.08,
        min_plane_area_m2: float = 4.0,
        max_gap_area_m2: float = 2.5,
        min_roof_area_m2: float = 8.0,
        max_drop_m: float = 30.0,
        min_drop_m: float = 0.8,
        min_roof_density: float = 0.55,
        max_existing_wall: float = 0.35,
        include_walls: bool = False,
    ) -> None:
        self.cell = float(cell_m)
        self.min_plane_area = float(min_plane_area_m2)
        self.max_gap_area = float(max_gap_area_m2)
        self.min_roof_area = float(min_roof_area_m2)
        self.max_drop = float(max_drop_m)
        self.min_drop = float(min_drop_m)
        self.min_roof_density = float(min_roof_density)
        self.max_existing_wall = float(max_existing_wall)
        self.include_walls = bool(include_walls)
        self.logger = get_logger()

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _peaks(values: np.ndarray, weights: np.ndarray, width: float,
               min_weight: float) -> List[Tuple[float, float]]:
        """Histogram peaks of `values` weighted by area, one entry per plane."""
        if values.size == 0:
            return []
        lo, hi = float(values.min()), float(values.max())
        if hi - lo < width:
            return [(0.5 * (lo + hi), float(weights.sum()))]
        edges = np.arange(lo, hi + width, width)
        idx = np.clip(np.digitize(values, edges) - 1, 0, edges.size - 2)
        acc = np.zeros(edges.size - 1)
        np.add.at(acc, idx, weights)
        out: List[Tuple[float, float]] = []
        taken = np.zeros(acc.size, dtype=bool)
        for _ in range(12):
            k = int(np.argmax(np.where(taken, -1.0, acc)))
            if acc[k] < min_weight:
                break
            span = slice(max(0, k - 1), min(acc.size, k + 2))
            sel = (idx >= span.start) & (idx < span.stop)
            if sel.any():
                w = weights[sel]
                out.append((float((values[sel] * w).sum() / w.sum()), float(w.sum())))
            taken[span] = True
        return out

    def _grid(self, u: np.ndarray, v: np.ndarray):
        """Occupancy grid over a plane's own coordinates, at `self.cell`."""
        u0, v0 = float(u.min()), float(v.min())
        iu = np.floor((u - u0) / self.cell).astype(np.int64)
        iv = np.floor((v - v0) / self.cell).astype(np.int64)
        w, h = int(iu.max()) + 1, int(iv.max()) + 1
        if w < 3 or h < 3 or w * h > 40_000_000:
            return None
        occ = np.zeros((h, w), dtype=bool)
        occ[iv, iu] = True
        return occ, u0, v0, iu, iv

    @staticmethod
    def _quads(centres: np.ndarray, e1: np.ndarray, e2: np.ndarray, half: float,
               flip: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Two triangles per cell centre, wound to follow `flip`."""
        a = centres + (-e1 - e2) * half
        b = centres + (e1 - e2) * half
        c = centres + (e1 + e2) * half
        d = centres + (-e1 + e2) * half
        v = np.concatenate([a, b, c, d], axis=0)
        n = centres.shape[0]
        i0 = np.arange(n)
        t1 = np.column_stack([i0, i0 + n, i0 + 2 * n])
        t2 = np.column_stack([i0, i0 + 2 * n, i0 + 3 * n])
        f = np.vstack([t1, t2])
        if flip.any():
            fl = np.concatenate([flip, flip])
            f[fl] = f[fl][:, ::-1]
        return v, f

    # ------------------------------------------------------------------ stages

    def _fill_planar_holes(self, mesh: trimesh.Trimesh, planes) -> List[trimesh.Trimesh]:
        """Closes holes that observed surface surrounds on all sides."""
        from scipy import ndimage as ndi

        tc = np.asarray(mesh.triangles_center)
        out: List[trimesh.Trimesh] = []
        cell_area = self.cell * self.cell
        max_cells = max(1, int(self.max_gap_area / cell_area))
        for n, off, _sel in planes:
            # Occupancy has to come from every face lying on the plane, not just the
            # ones the peak search assigned to it. Detection splits one facade across
            # several offsets, and a grid built from one slice is full of holes that
            # the other slices already cover -- filling those was inventing 144 m2 of
            # wall on a 773 m2 mesh, which is precisely the over-guessing to avoid.
            sel = np.flatnonzero(np.abs(tc @ n + off) < 0.15)
            if sel.size < 64:
                continue
            e1 = np.array([n[1], -n[0], 0.0])
            if np.linalg.norm(e1) < 1e-6:
                e1 = np.array([1.0, 0.0, 0.0])
            e1 /= np.linalg.norm(e1)
            e2 = np.cross(n, e1)
            p = tc[sel]
            g = self._grid(p @ e1, p @ e2)
            if g is None:
                continue
            occ, u0, v0, _, _ = g
            closed = ndi.binary_closing(occ, np.ones((5, 5), dtype=bool))
            holes = ndi.binary_fill_holes(closed) & ~occ
            if not holes.any():
                continue
            lab, cnt = ndi.label(holes)
            if cnt == 0:
                continue
            size = np.bincount(lab.ravel())
            keep = np.flatnonzero((size[1:] <= max_cells)) + 1
            if keep.size == 0:
                continue
            take = np.isin(lab, keep) & holes
            iv, iu = np.nonzero(take)
            if iu.size == 0:
                continue
            cu = u0 + (iu + 0.5) * self.cell
            cv = v0 + (iv + 0.5) * self.cell
            centres = cu[:, None] * e1 + cv[:, None] * e2 + (-off) * n
            v, f = self._quads(centres, e1, e2, 0.5 * self.cell,
                               np.zeros(iu.size, dtype=bool))
            out.append(trimesh.Trimesh(v, f, process=False))
        return out

    def _walls_under_roofs(self, mesh: trimesh.Trimesh, ground: float):
        """
        Extrudes the rim of every observed roof straight down.

        A roof seen from above with open air under its edge is the one gap in a
        single-pass flight whose answer is not a guess: the wall is where the rim is,
        it is vertical, and it stops at the first surface below -- another roof, a
        balcony, or the ground the mesh is already levelled on.

        What makes this safe is refusing to run on something that is not a roof. A
        low pass over a street produces a hundred square metres of up-facing surface
        that is window sills, balconies and torn fragments spread over a ten metre
        band, and closing that scatter into a blob invents a footprint whose rim is
        nowhere near a wall -- extruding it hangs a thousand square metres of
        invented panel in mid-air on a mesh that measured seven hundred. So a roof
        has to look like a roof first: its up-facing surface must actually tile the
        footprint it claims, and each patch must be big and solid on its own. On a
        flight that never saw a roof this stage correctly does nothing.
        """
        from scipy import ndimage as ndi

        tc = np.asarray(mesh.triangles_center)
        fn = np.asarray(mesh.face_normals)
        fa = np.asarray(mesh.area_faces)
        up = fn[:, 2] > 0.80
        if not up.any():
            return [], 0.0
        cell = max(self.cell, 0.12)
        cell_area = cell * cell
        xy = tc[:, :2]
        x0, y0 = xy[:, 0].min(), xy[:, 1].min()
        ix = np.floor((xy[:, 0] - x0) / cell).astype(np.int64)
        iy = np.floor((xy[:, 1] - y0) / cell).astype(np.int64)
        w, h = int(ix.max()) + 1, int(iy.max()) + 1
        if w < 4 or h < 4 or w * h > 20_000_000:
            return [], 0.0
        # Height of the highest surface in each column, so a rim knows what it stands
        # on, and how much wall each column already has, so an observed facade is not
        # buried under an inferred copy of itself.
        top = np.full((h, w), -np.inf)
        np.maximum.at(top, (iy, ix), tc[:, 2])
        varea = np.zeros((h, w))
        vsel = np.abs(fn[:, 2]) < 0.45
        if vsel.any():
            np.add.at(varea, (iy[vsel], ix[vsel]), fa[vsel])
        parts: List[trimesh.Trimesh] = []
        area = 0.0
        used: List[float] = []
        for z_roof, _w in self._peaks(tc[up, 2], fa[up], 0.30, self.min_roof_area):
            # Neighbouring histogram bins peak on the same roof; taking both doubles
            # the walls under it.
            if any(abs(z_roof - z) < 0.9 for z in used):
                continue
            band = up & (np.abs(tc[:, 2] - z_roof) < 0.45)
            band_area = float(fa[band].sum())
            if band_area < self.min_roof_area:
                continue
            occ = np.zeros((h, w), dtype=bool)
            occ[iy[band], ix[band]] = True
            # A roof tiles its own footprint. Scattered ledges do not.
            if band_area < self.min_roof_density * occ.sum() * cell_area:
                continue
            solid = ndi.binary_fill_holes(ndi.binary_closing(occ, np.ones((5, 5), bool)))
            lab, n_lab = ndi.label(solid)
            if n_lab == 0:
                continue
            # Only patches that are large and mostly filled before closing count.
            sizes = np.bincount(lab.ravel(), minlength=n_lab + 1)
            filled = np.bincount(lab[occ].ravel(), minlength=n_lab + 1)
            good = np.flatnonzero(
                (sizes * cell_area >= self.min_roof_area)
                & (filled >= self.min_roof_density * sizes)
            )
            good = good[good > 0]
            if good.size == 0:
                continue
            keep = np.isin(lab, good)
            used.append(z_roof)
            rim = keep & ~ndi.binary_erosion(keep, np.ones((3, 3), bool))
            ry, rx = np.nonzero(rim)
            if ry.size == 0:
                continue
            # Stop on the highest surface that sits at least a little below the roof.
            below = np.where(top[ry, rx] < z_roof - 0.6, top[ry, rx], -np.inf)
            floor = np.where(np.isfinite(below), below, ground)
            drop = z_roof - floor
            ok = (drop > self.min_drop) & (drop < self.max_drop)
            # A column that already carries most of a wall needs no second one. Area
            # is the test, not presence: one stray triangle is not a facade.
            ok &= varea[ry, rx] < self.max_existing_wall * cell * drop
            if not ok.any():
                continue
            ry, rx, floor, drop = ry[ok], rx[ok], floor[ok], drop[ok]
            cx = x0 + (rx + 0.5) * cell
            cy = y0 + (ry + 0.5) * cell
            # Outward normal from the roof centroid, so the panel faces the world.
            gx, gy = cx.mean(), cy.mean()
            dx, dy = cx - gx, cy - gy
            m = np.maximum(np.hypot(dx, dy), 1e-6)
            nx, ny = dx / m, dy / m
            centres = np.column_stack([cx, cy, floor + 0.5 * drop])
            e1 = np.column_stack([-ny, nx, np.zeros_like(nx)])
            e2 = np.zeros_like(e1)
            e2[:, 2] = 1.0
            # Each rim cell gives one panel. Cut to exactly one cell they meet edge to
            # edge and the seams show as hairlines; a little overlap reads as one wall.
            half = 0.58 * cell
            a = centres - e1 * half - e2 * (0.5 * drop)[:, None]
            b = centres + e1 * half - e2 * (0.5 * drop)[:, None]
            c = centres + e1 * half + e2 * (0.5 * drop)[:, None]
            dd = centres - e1 * half + e2 * (0.5 * drop)[:, None]
            v = np.concatenate([a, b, c, dd], axis=0)
            k = centres.shape[0]
            i0 = np.arange(k)
            f = np.vstack([
                np.column_stack([i0, i0 + k, i0 + 2 * k]),
                np.column_stack([i0, i0 + 2 * k, i0 + 3 * k]),
            ])
            parts.append(trimesh.Trimesh(v, f, process=False))
            area += float((cell * drop).sum())
        return parts, area

    # ------------------------------------------------------------------ entry

    def _planes(self, mesh: trimesh.Trimesh):
        """Detected planes as (unit normal, offset, face indices on that plane)."""
        tc = np.asarray(mesh.triangles_center)
        fn = np.asarray(mesh.face_normals)
        fa = np.asarray(mesh.area_faces)
        planes = []
        vsel = np.flatnonzero(np.abs(fn[:, 2]) < 0.35)
        if vsel.size:
            az = np.mod(np.arctan2(fn[vsel, 1], fn[vsel, 0]), np.pi)
            for a, _w in self._peaks(az, fa[vsel], np.deg2rad(4.0), self.min_plane_area):
                n = np.array([np.cos(a), np.sin(a), 0.0])
                near = vsel[np.abs(np.mod(az - a + 0.5 * np.pi, np.pi) - 0.5 * np.pi) < np.deg2rad(12)]
                if near.size < 64:
                    continue
                d = tc[near] @ n
                for off, _ in self._peaks(d, fa[near], 0.20, self.min_plane_area):
                    sel = near[np.abs(d - off) < 0.12]
                    if sel.size >= 64 and float(fa[sel].sum()) >= self.min_plane_area:
                        planes.append((n, -off, sel))
        hsel = np.flatnonzero(np.abs(fn[:, 2]) > 0.85)
        if hsel.size:
            z = tc[hsel, 2]
            for off, _ in self._peaks(z, fa[hsel], 0.20, self.min_plane_area):
                sel = hsel[np.abs(z - off) < 0.12]
                if sel.size >= 64 and float(fa[sel].sum()) >= self.min_plane_area:
                    planes.append((np.array([0.0, 0.0, 1.0]), -off, sel))
        # Near-duplicate planes cost time and, worse, each one re-fills the same gaps.
        keep = []
        for n, off, sel in planes:
            if any(abs(float(n @ n2)) > 0.985 and abs(off - off2) < 0.35
                   for n2, off2, _ in keep):
                continue
            keep.append((n, off, sel))
        return keep

    def complete(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """
        Returns the mesh with inferred surface appended and tagged.

        Only the planar gap fill goes into the delivered mesh. The wall extrusion is
        a building envelope, not a measurement: on a pass down one side of a street it
        adds more surface than the flight observed, and it stands in front of the
        facade that was observed, so a viewer sees an inferred slab instead of the
        real thing. It is exported beside the model as its own artifact instead --
        `envelope()` -- where it can be looked at and measured knowing what it is.
        """
        if mesh is None or len(mesh.faces) < 5000:
            return mesh
        try:
            base = len(mesh.faces)
            planes = self._planes(mesh)
            gaps = self._fill_planar_holes(mesh, planes) if planes else []
            parts = [p for p in gaps if p is not None and len(p.faces)]
            wall_area = 0.0
            if self.include_walls:
                ground = float(np.percentile(np.asarray(mesh.vertices)[:, 2], 0.5))
                walls, wall_area = self._walls_under_roofs(mesh, ground)
                parts += [p for p in walls if p is not None and len(p.faces)]
            if not parts:
                self.logger.info(
                    "Structural completion found nothing the observed geometry decides; "
                    "mesh left as measured."
                )
                return mesh
            add = trimesh.util.concatenate(parts)
            gap_area = float(sum(p.area for p in gaps))
            src = getattr(mesh.visual, "vertex_colors", None)
            out = trimesh.util.concatenate([mesh, add])
            if src is not None and len(src) == len(mesh.vertices):
                from scipy.spatial import cKDTree

                src = np.asarray(src)
                tree = cKDTree(np.asarray(mesh.vertices))
                idx = tree.query(np.asarray(add.vertices), k=1)[1]
                out.visual.vertex_colors = np.vstack([src, src[idx]])
            out.metadata = dict(mesh.metadata or {})
            out.metadata["inferred_faces"] = np.arange(base, len(out.faces))
            out.metadata["inferred_area_m2"] = float(add.area)
            frac = 100.0 * (len(out.faces) - base) / max(1, len(out.faces))
            extra = (
                f" and raised {wall_area:.1f} m2 of wall under observed roof rims"
                if self.include_walls else ""
            )
            self.logger.info(
                f"Structural completion: closed {gap_area:.1f} m2 of enclosed gaps on "
                f"{len(planes)} detected planes{extra} -- {len(out.faces) - base} "
                f"triangles, {frac:.1f}% of the mesh, tagged inferred rather than measured."
            )
            return out
        except Exception as exc:
            self.logger.warning(f"Structural completion skipped: {exc}")
            return mesh

    def envelope(self, mesh: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
        """
        The LOD1 building envelope implied by the observed roofs, on its own.

        A roof does not float, so the wall under its rim exists -- but on a single
        pass the flight saw one facade of it at best, and a thousand square metres of
        implied wall on seven hundred of measured surface would swamp the model it was
        meant to complete. Kept separate, it answers the question the delivered mesh
        cannot ("what shape is this building?") without ever being mistaken for
        evidence. Returns None when no observed roof supports one.
        """
        if mesh is None or len(mesh.faces) < 5000:
            return None
        try:
            ground = float(np.percentile(np.asarray(mesh.vertices)[:, 2], 0.5))
            walls, wall_area = self._walls_under_roofs(mesh, ground)
            walls = [p for p in walls if p is not None and len(p.faces)]
            if not walls:
                return None
            env = trimesh.util.concatenate(walls)
            env.visual.vertex_colors = np.tile(
                np.asarray([190, 190, 195, 255], dtype=np.uint8), (len(env.vertices), 1)
            )
            env.metadata = {"inferred_faces": np.arange(len(env.faces)),
                            "inferred_area_m2": float(wall_area)}
            self.logger.info(
                f"Building envelope: {wall_area:.1f} m2 of wall inferred under observed "
                f"roof rims, {len(env.faces)} triangles, exported separately as "
                f"model_envelope so the measured mesh stays measured."
            )
            return env
        except Exception as exc:
            self.logger.warning(f"Building envelope skipped: {exc}")
            return None
