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
        
        # Calculate scene height distribution (ENU Z coordinates)
        positions = world.store.get_all_positions()
        if len(positions) == 0:
            return counts
            
        z_min = float(np.min(positions[:, 2]))
        z_max = float(np.max(positions[:, 2]))
        z_range = max(1.0, z_max - z_min)
        
        for elem in world.store.elements.values():
            if elem.state == WorldElementState.REJECTED:
                continue
                
            pos = elem.position
            normal = elem.normal
            color = elem.color  # RGB [0..255]
            
            r, g, b = float(color[0]), float(color[1]), float(color[2])
            tot_rgb = max(1.0, r + g + b)
            
            # Normal verticality (ENU Z is up)
            # nz ~ 1.0 -> horizontal facing up (ground or roof)
            # nz ~ 0.0 -> vertical wall / facade
            # nz < -0.2 -> facing downward / overhang
            nz = float(normal[2])
            is_vertical = abs(nz) < 0.35
            is_horizontal_up = nz > 0.70
            
            rel_height = (pos[2] - z_min) / z_range
            
            # 1. Vegetation detection (Excess Green Index: 2G - R - B)
            ex_green = (2.0 * g - r - b) / tot_rgb
            if ex_green > 0.18 and not is_vertical:
                elem.semantic_class = SemanticClass.VEGETATION
                elem.dynamic_probability = 0.05
            # 2. Water detection (Blue-Green dominant with low variance, flat, low altitude)
            elif (b > r + 15) and is_horizontal_up and rel_height < 0.15:
                elem.semantic_class = SemanticClass.WATER
                elem.dynamic_probability = 0.10
            # 3. Facade / Vertical Wall
            elif is_vertical and rel_height > 0.10:
                elem.semantic_class = SemanticClass.FACADE
                elem.dynamic_probability = 0.0
            # 4. Roof (Elevated horizontal surface)
            elif is_horizontal_up and rel_height > 0.35:
                elem.semantic_class = SemanticClass.ROOF
                elem.dynamic_probability = 0.0
            # 5. Road / Pavement (Dark low surface with low saturation)
            elif is_horizontal_up and rel_height <= 0.25 and tot_rgb < 280:
                elem.semantic_class = SemanticClass.ROAD
                elem.dynamic_probability = 0.0
            # 6. General Ground
            elif rel_height <= 0.30:
                elem.semantic_class = SemanticClass.GROUND
                elem.dynamic_probability = 0.0
            # 7. Building General
            elif rel_height > 0.25:
                elem.semantic_class = SemanticClass.BUILDING
                elem.dynamic_probability = 0.0
            else:
                elem.semantic_class = SemanticClass.UNKNOWN
                
            # Dynamic Object Check:
            # If observation count is low (1) in an open road/ground area, or fast moving color signature
            if elem.observation_count == 1 and elem.semantic_class in [SemanticClass.ROAD, SemanticClass.GROUND]:
                if elem.reprojection_error > 3.0:
                    elem.dynamic_probability = 0.85
                    elem.state = WorldElementState.REJECTED
                    dynamic_rejected_count += 1
                    continue
                    
            counts[elem.semantic_class.value] += 1
            
        self.logger.info(
            f"Semantic classification complete: Facade={counts['facade']}, Roof={counts['roof']}, Ground={counts['ground']}, Vegetation={counts['vegetation']}, Road={counts['road']}, Filtered Dynamics={dynamic_rejected_count}"
        )
        return counts
