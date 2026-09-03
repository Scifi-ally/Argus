"""
Semantic Classification and Dynamic Object Detection & Filtering for SinglePass3D.
Classifies surface elements into 10 semantic categories and filters transient moving objects.
"""

from __future__ import annotations
from typing import Dict, List, Optional
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import (
    SemanticClass,
    WorldElement,
    WorldElementState,
)
from singlepass3d.metric_world.persistent_world import PersistentWorld


class SemanticDynamicsFilter:
    """
    Classifies 3D surfels into semantic categories and identifies dynamic objects.
    """
    def __init__(self):
        self.logger = get_logger()

    def process_world(self, world: PersistentWorld) -> Dict[str, int]:
        """
        Applies semantic priors and dynamic object filtering across all world elements.
        """
        self.logger.info(f"Classifying semantics and filtering dynamics across {len(world.store)} elements...")
        
        counts: Dict[str, int] = {sc.value: 0 for sc in SemanticClass}
        dynamic_rejected_count = 0
        
        # Robust ground plane elevation datum (10th percentile of lowest points)
        positions = world.store.get_all_positions()
        if len(positions) == 0:
            return counts
            
        z_ground = float(np.percentile(positions[:, 2], 10))
        z_max = float(np.max(positions[:, 2]))
        z_span = max(1.0, z_max - z_ground)
        
        for elem in world.store.elements.values():
            if elem.state == WorldElementState.REJECTED:
                continue
                
            pos = elem.position
            normal = elem.normal
            color = elem.color  # RGB [0..255]
            
            r, g, b = float(color[0]), float(color[1]), float(color[2])
            tot_rgb = max(1.0, r + g + b)
            
            # Normal verticality (ENU Z is up)
            nz = float(normal[2])
            is_vertical = abs(nz) < 0.40
            is_horizontal_up = nz > 0.65
            
            # Elevation relative to estimated ground plane
            delta_z = float(pos[2] - z_ground)
            rel_height = max(0.0, delta_z / z_span)
            
            # Color metrics
            ex_green = (2.0 * g - r - b) / tot_rgb
            saturation = (max(r, g, b) - min(r, g, b)) / max(1.0, max(r, g, b))
            
            # 1. Vegetation (Excess Green Index or high non-vertical foliage)
            if ex_green > 0.14 and not is_vertical and delta_z > -0.5:
                elem.semantic_class = SemanticClass.VEGETATION
                elem.dynamic_probability = 0.05
            # 2. Water (Blue-dominant, low variance, flat, near ground level)
            elif (b > r + 12 and b > g + 8) and is_horizontal_up and delta_z <= 1.0:
                elem.semantic_class = SemanticClass.WATER
                elem.dynamic_probability = 0.05
            # 3. Dynamic Moving Vehicle or Pedestrian Detection:
            # Sits just above road level (0.2m - 2.8m), with transient observation count or high reprojection residual
            elif 0.20 <= delta_z <= 2.8 and (elem.reprojection_error > 2.2 or elem.observation_count <= 2):
                if delta_z <= 2.0 and saturation > 0.15:
                    elem.semantic_class = SemanticClass.VEHICLE
                    elem.dynamic_probability = 0.85
                    elem.state = WorldElementState.REJECTED
                    dynamic_rejected_count += 1
                    counts[elem.semantic_class.value] += 1
                    continue
                elif delta_z <= 1.8:
                    elem.semantic_class = SemanticClass.PERSON
                    elem.dynamic_probability = 0.80
                    elem.state = WorldElementState.REJECTED
                    dynamic_rejected_count += 1
                    counts[elem.semantic_class.value] += 1
                    continue
            # 4. Facade / Vertical Architectural Wall
            elif is_vertical and delta_z > 1.2:
                elem.semantic_class = SemanticClass.FACADE
                elem.dynamic_probability = 0.0
            # 5. Roof (Elevated horizontal architectural surface)
            elif is_horizontal_up and delta_z > 2.8:
                elem.semantic_class = SemanticClass.ROOF
                elem.dynamic_probability = 0.0
            # 6. Road / Asphalt Pavement (Flat, near ground level, neutral low-saturation color)
            elif is_horizontal_up and -0.8 <= delta_z <= 0.4 and saturation < 0.20 and tot_rgb < 360:
                elem.semantic_class = SemanticClass.ROAD
                elem.dynamic_probability = 0.0
            # 7. General Terrain / Ground
            elif delta_z <= 0.8:
                elem.semantic_class = SemanticClass.GROUND
                elem.dynamic_probability = 0.0
            # 8. Building Envelope (General structure)
            elif delta_z > 2.0:
                elem.semantic_class = SemanticClass.BUILDING
                elem.dynamic_probability = 0.0
            else:
                elem.semantic_class = SemanticClass.UNKNOWN
                
            # Secondary dynamic check for transient ground outliers
            if elem.observation_count == 1 and elem.semantic_class in [SemanticClass.ROAD, SemanticClass.GROUND]:
                if elem.reprojection_error > 2.5:
                    elem.dynamic_probability = 0.80
                    elem.state = WorldElementState.REJECTED
                    dynamic_rejected_count += 1
                    continue
                    
            counts[elem.semantic_class.value] += 1
            
        self.logger.info(
            f"Semantic classification complete: Facade={counts['facade']}, Roof={counts['roof']}, "
            f"Ground={counts['ground']}, Road={counts['road']}, Vegetation={counts['vegetation']}, "
            f"Vehicles={counts['vehicle']}, Pedestrians={counts['person']}, Filtered Dynamics={dynamic_rejected_count}"
        )
        return counts
