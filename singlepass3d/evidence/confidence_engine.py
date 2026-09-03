"""
Multi-Factor World Confidence Engine for SinglePass3D.
Evaluates multi-view support, baseline triangulation angles, reprojection errors,
sharpness, and semantic consistency to compute hierarchical confidence ratings.
"""

from __future__ import annotations
from typing import Dict, List, Optional
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import (
    ConfidenceLevel,
    Provenance,
    SemanticClass,
    Trajectory,
    WorldElement,
    WorldElementState,
)
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.sensor.video_indexer import VideoIndexer


class ConfidenceEngine:
    """
    Computes rigorous multi-factor surface confidence scores and classifies surfels into HIGH, MEDIUM, LOW, UNKNOWN.
    """
    def __init__(self):
        self.logger = get_logger()

    def evaluate_world_confidence(
        self,
        world: PersistentWorld,
        trajectory: Trajectory,
        indexer: VideoIndexer
    ) -> Dict[str, Any]:
        """
        Computes composite confidence scores for every world element in the persistent store.
        """
        self.logger.info(f"Evaluating world confidence hierarchy across {len(world.store)} elements...")
        
        counts = {
            ConfidenceLevel.HIGH: 0,
            ConfidenceLevel.MEDIUM: 0,
            ConfidenceLevel.LOW: 0,
            ConfidenceLevel.UNKNOWN: 0
        }
        
        for elem in world.store.elements.values():
            if elem.state == WorldElementState.REJECTED:
                elem.confidence_level = ConfidenceLevel.UNKNOWN
                elem.confidence_score = 0.0
                counts[ConfidenceLevel.UNKNOWN] += 1
                continue
                
            # Factor 1: Number of supporting views (0 to 1)
            num_views = len(elem.supporting_frames)
            view_score = np.clip((num_views - 1) / 3.0, 0.0, 1.0)
            
            # Factor 2: Triangulation baseline angle
            angle_score = 0.5
            if len(elem.supporting_rays) >= 2:
                r0 = elem.supporting_rays[0]
                r1 = elem.supporting_rays[-1]
                dot = np.clip(np.dot(r0, r1), -1.0, 1.0)
                angle_deg = np.degrees(np.arccos(dot))
                angle_score = np.clip(angle_deg / 15.0, 0.0, 1.0)
                
            # Factor 3: Reprojection error score (lower is better)
            err = elem.reprojection_error
            reproj_score = np.clip(1.0 - (err / 4.0), 0.0, 1.0)
            
            # Factor 4: Model & GPS confidence
            model_score = elem.model_confidence
            gps_score = elem.gps_trajectory_confidence
            
            # Factor 5: Semantic & dynamic penalty
            dynamic_penalty = 1.0 - elem.dynamic_probability
            semantic_mult = 1.0
            if elem.semantic_class == SemanticClass.VEGETATION:
                semantic_mult = 0.7  # vegetation has lower hard-surface confidence
            elif elem.semantic_class in [SemanticClass.BUILDING, SemanticClass.FACADE, SemanticClass.ROOF]:
                semantic_mult = 1.15  # buildings have strong geometric priors
                
            # Composite weighted confidence formula
            raw_score = (
                0.30 * view_score +
                0.25 * reproj_score +
                0.20 * angle_score +
                0.15 * model_score +
                0.10 * gps_score
            ) * dynamic_penalty * semantic_mult
            
            score = float(np.clip(raw_score, 0.0, 1.0))
            elem.confidence_score = score
            
            # Hierarchy Classification
            if num_views >= 2 and err < 3.0 and score >= 0.70:
                elem.confidence_level = ConfidenceLevel.HIGH
                if elem.provenance == Provenance.OBSERVED:
                    elem.provenance = Provenance.MULTI_VIEW_SUPPORTED
            elif num_views >= 1 and score >= 0.40:
                elem.confidence_level = ConfidenceLevel.MEDIUM
            elif score > 0.15:
                elem.confidence_level = ConfidenceLevel.LOW
            else:
                elem.confidence_level = ConfidenceLevel.UNKNOWN
                
            counts[elem.confidence_level] += 1
            
        self.logger.info(
            f"Confidence evaluation complete: HIGH={counts[ConfidenceLevel.HIGH]}, MEDIUM={counts[ConfidenceLevel.MEDIUM]}, LOW={counts[ConfidenceLevel.LOW]}, UNKNOWN={counts[ConfidenceLevel.UNKNOWN]}"
        )
        return {
            "high": counts[ConfidenceLevel.HIGH],
            "medium": counts[ConfidenceLevel.MEDIUM],
            "low": counts[ConfidenceLevel.LOW],
            "unknown": counts[ConfidenceLevel.UNKNOWN],
        }
