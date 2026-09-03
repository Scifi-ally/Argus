"""
3D Gaussian Splatting PLY Exporter for SinglePass3D.
Exports verified surfels into 3D Gaussian Splats with covariance ellipsoids and spherical harmonics colors.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import WorldElement, WorldElementState, rot_to_quat
from singlepass3d.metric_world.persistent_world import PersistentWorld


class AppearanceSplatExporter:
    """
    Exports persistent world elements to 3D Gaussian Splats PLY format.
    """
    def __init__(self):
        self.logger = get_logger()

    def export_gaussian_splats_ply(
        self,
        world: PersistentWorld,
        output_path: str | Path
    ) -> bool:
        """
        Writes standard 3D Gaussian Splatting PLY file.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        
        elements = [e for e in world.store.elements.values() if e.state != WorldElementState.REJECTED]
        N = len(elements)
        if N == 0:
            return False
            
        self.logger.info(f"Exporting {N} 3D Gaussian Splats to {out.name}...")
        
        # Binary PLY Header
        header = f"""ply
format binary_little_endian 1.0
element vertex {N}
property float x
property float y
property float z
property float nx
property float ny
property float nz
property uchar red
property uchar green
property uchar blue
property float f_dc_0
property float f_dc_1
property float f_dc_2
property float opacity
property float scale_0
property float scale_1
property float scale_2
property float rot_0
property float rot_1
property float rot_2
property float rot_3
end_header
"""
        
        # Prepare structured numpy array
        dtype = [
            ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
            ('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4'),
            ('red', 'u1'), ('green', 'u1'), ('blue', 'u1'),
            ('f_dc_0', 'f4'), ('f_dc_1', 'f4'), ('f_dc_2', 'f4'),
            ('opacity', 'f4'),
            ('scale_0', 'f4'), ('scale_1', 'f4'), ('scale_2', 'f4'),
            ('rot_0', 'f4'), ('rot_1', 'f4'), ('rot_2', 'f4'), ('rot_3', 'f4'),
        ]
        
        data = np.empty(N, dtype=dtype)
        
        # Spherical harmonics factor C0 = 0.28209479177387814
        C0 = 0.28209479177387814
        
        for i, elem in enumerate(elements):
            pos = elem.position
            normal = elem.normal
            color_norm = (elem.color / 255.0 - 0.5) / C0  # convert [0..1] RGB to SH DC component
            
            # Rotation quaternion aligning [0, 0, 1] to normal
            # Simple rotation matrix from z-axis to normal
            z_axis = np.array([0.0, 0.0, 1.0])
            v = np.cross(z_axis, normal)
            s = np.linalg.norm(v)
            c = np.dot(z_axis, normal)
            if s > 1e-6:
                vx = np.array([
                    [0, -v[2], v[1]],
                    [v[2], 0, -v[0]],
                    [-v[1], v[0], 0]
                ])
                R = np.eye(3) + vx + (vx @ vx) * ((1.0 - c) / (s**2))
            else:
                R = np.eye(3) if c > 0 else -np.eye(3)
                
            q = rot_to_quat(R)
            
            scale = np.log(max(1e-4, world.voxel_size_m * 0.8))  # log scale
            opacity = 4.0 if elem.confidence_score > 0.6 else 2.0  # logit opacity
            
            data['x'][i] = pos[0]
            data['y'][i] = pos[1]
            data['z'][i] = pos[2]
            data['nx'][i] = normal[0]
            data['ny'][i] = normal[1]
            data['nz'][i] = normal[2]
            data['red'][i] = int(np.clip(elem.color[0], 0, 255))
            data['green'][i] = int(np.clip(elem.color[1], 0, 255))
            data['blue'][i] = int(np.clip(elem.color[2], 0, 255))
            data['f_dc_0'][i] = color_norm[0]
            data['f_dc_1'][i] = color_norm[1]
            data['f_dc_2'][i] = color_norm[2]
            data['opacity'][i] = opacity
            data['scale_0'][i] = scale
            data['scale_1'][i] = scale
            data['scale_2'][i] = scale
            data['rot_0'][i] = q[0]
            data['rot_1'][i] = q[1]
            data['rot_2'][i] = q[2]
            data['rot_3'][i] = q[3]
            
        with open(out, 'wb') as f:
            f.write(header.encode('ascii'))
            f.write(data.tobytes())
            
        self.logger.info(f"Gaussian splat export written successfully to {out.name}")
        return True
