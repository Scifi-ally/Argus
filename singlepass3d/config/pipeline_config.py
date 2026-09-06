"""
Configuration and quality presets for SinglePass3D.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class QualityPreset:
    name: str
    proxy_max_dim: int
    tracking_step: int
    min_keyframe_parallax_deg: float
    window_size: int
    window_overlap: int
    voxel_size_m: float
    poisson_depth: int
    texture_resolution: int
    max_features: int
    use_classical_sfm_verification: bool
    structural_completion: bool
    generative_completion: bool
    high_res_refinement: bool
    gaussian_splat_export: bool

    # --- Dense plane-sweep MVS (the primary source of fine detail) ---
    # Working resolution of the cost volume. It sets the lateral sampling of the depth
    # map -- depth over focal length in pixels -- and measurement says that is not
    # what bounds the finished mesh. Controlled A/B on eight frames, ZNCC window
    # scaled with the resolution so both passes correlate the same patch of ground:
    #
    #            lateral   per-pixel   cross-view   fused    faces
    #   960 px    2.0 cm    30.5 cm      4.6 cm     4.6 cm   399822
    #  1920 px    1.0 cm    16.4 cm      4.6 cm     4.6 cm   378461
    #
    # Lateral sampling halved and per-pixel triangulation precision halved, exactly as
    # z^2/(b*f) predicts -- and the depth maps still agreed with each other to the same
    # 4.6 cm, so the earned voxel did not move at all, for 4x the compute. The floor is
    # correlated error (residual relative pose, amplified by range over baseline), and
    # image sampling does not touch it. A first attempt at this experiment left the
    # window at 11 px and lost half the coverage (18% -> 12%), which is a separate
    # effect worth knowing: the window has to grow with the resolution or it covers a
    # quarter of the ground patch. Escalate baseline and source-view count for quality,
    # not this.
    mvs_max_dim: int = 960          # working resolution of the cost volume
    mvs_num_planes: int = 64        # depth hypotheses at the coarsest level
    # Source views matched against each reference. This is the cheapest coverage
    # lever measured on this footage: going 3 -> 6 raised the surviving surface from
    # 18% to 21% of the frame at an unchanged 4.3 cm fused voxel (+13% faces), because
    # every extra source is another chance both to find a match at all and to have it
    # corroborated by two views. Cost is roughly linear in this number. It pays off
    # only with the whole-flight source pool wired up, since the point is to reach
    # frames with usable baseline rather than merely adjacent ones.
    mvs_num_src_views: int = 6      # source views matched against each reference
    mvs_levels: int = 3             # coarse-to-fine pyramid levels
    # ZNCC support window, in pixels of the working resolution. It has to grow with
    # mvs_max_dim to keep covering the same patch of scene: a 7 px window that was
    # well conditioned at 640 px sees a third as much texture at 1920 px and starts
    # matching noise. Measured on the synthetic rig, 960 px with a 9 px window beats
    # 960 px with a 7 px window on both error and coverage.
    mvs_zncc_win: int = 9           # ZNCC support window
    mvs_geo_consistency_views: int = 2
    mvs_min_confidence: float = 0.15

    # --- Volumetric TSDF fusion of the dense depth maps ---
    tsdf_voxel_m: float = 0.08
    tsdf_sdf_trunc_mult: float = 4.0

    # Longest run of frames that may pass without a reconstruction keyframe. Dense
    # fusion improves with the number of depth maps, so this is much tighter than the
    # interval a pose graph alone would need.
    keyframe_max_frame_gap: int = 8

    # --- Mesh finishing ---
    mesh_smooth_iterations: int = 0  # 0 = keep crisp ridges and corners
    target_mesh_faces: int = 250000   # Quadric error decimation target for sharp UV texturing
    include_walls: bool = True       # Extrude rear/side walls under observed roofs for single-pass blind spots
    export_geospatial: bool = True   # Generate Orthomosaic & DSM GeoTIFF rasters


PRESETS: Dict[str, QualityPreset] = {
    "fast": QualityPreset(
        name="fast",
        proxy_max_dim=960,
        tracking_step=1,
        min_keyframe_parallax_deg=2.0,
        window_size=10,
        window_overlap=4,
        voxel_size_m=0.05,
        poisson_depth=9,
        texture_resolution=2048,
        max_features=2000,
        use_classical_sfm_verification=True,
        structural_completion=True,
        generative_completion=False,
        high_res_refinement=False,
        gaussian_splat_export=True,
        mvs_max_dim=640,
        mvs_num_planes=96,
        mvs_num_src_views=4,
        mvs_levels=2,
        mvs_zncc_win=7,
        tsdf_voxel_m=0.14,
        keyframe_max_frame_gap=10,
        target_mesh_faces=150000,
        include_walls=True,
    ),
    "balanced": QualityPreset(
        name="balanced",
        proxy_max_dim=1280,
        tracking_step=1,
        min_keyframe_parallax_deg=1.8,
        window_size=14,
        window_overlap=5,
        voxel_size_m=0.035,
        poisson_depth=10,
        texture_resolution=4096,
        max_features=3000,
        use_classical_sfm_verification=True,
        structural_completion=True,
        generative_completion=False,
        high_res_refinement=True,
        gaussian_splat_export=True,
        mvs_max_dim=960,
        # The coarse level is swept at a quarter resolution and the refinement levels
        # re-search a band around its winner whose width is inversely proportional to
        # this number, so a denser coarse search is not simply a better one: it narrows
        # the escape route from a coarse mistake. Measured on eight frames with the cost
        # volume aggregated, 96 planes beat 160 outright -- 20% of the frame surviving
        # against 19%, a 4.15 cm fused voxel against 4.20, 996k faces against 924k --
        # and took 77 s against 136. Raising it past this buys nothing on this footage.
        mvs_num_planes=96,
        mvs_num_src_views=6,
        mvs_levels=3,
        mvs_zncc_win=9,
        tsdf_voxel_m=0.10,
        keyframe_max_frame_gap=8,
        target_mesh_faces=300000,
        include_walls=True,
    ),
    "high": QualityPreset(
        name="high",
        proxy_max_dim=1920,
        tracking_step=1,
        min_keyframe_parallax_deg=1.4,
        window_size=18,
        window_overlap=6,
        voxel_size_m=0.020,
        poisson_depth=11,
        texture_resolution=4096,
        max_features=4000,
        use_classical_sfm_verification=True,
        structural_completion=True,
        generative_completion=False,
        high_res_refinement=True,
        gaussian_splat_export=True,
        mvs_max_dim=1280,
        mvs_num_planes=128,
        mvs_num_src_views=8,
        mvs_levels=3,
        mvs_zncc_win=13,   # 1280 * 0.0094, the ratio that holds the patch size
        tsdf_voxel_m=0.07,
        keyframe_max_frame_gap=6,
        target_mesh_faces=350000,
        include_walls=True,
    ),
    "ultra": QualityPreset(
        name="ultra",
        proxy_max_dim=1920,
        tracking_step=1,
        min_keyframe_parallax_deg=1.2,
        window_size=24,
        window_overlap=8,
        voxel_size_m=0.018,
        poisson_depth=11,
        texture_resolution=4096,
        max_features=5000,
        use_classical_sfm_verification=True,
        structural_completion=True,
        generative_completion=False,
        high_res_refinement=True,
        gaussian_splat_export=True,
        mvs_max_dim=1920,
        mvs_num_planes=160,
        mvs_num_src_views=10,
        mvs_levels=4,
        mvs_zncc_win=19,   # 1920 * 0.0094; an 11 px window here loses half the coverage
        tsdf_voxel_m=0.05,
        keyframe_max_frame_gap=5,
        target_mesh_faces=500000,
        include_walls=True,
    ),
}


@dataclass
class SinglePass3DConfig:
    # Basic Job metadata
    job_name: str = "singlepass3d_reconstruction"
    quality: str = "balanced"
    video_path: Optional[str] = None
    telemetry_path: Optional[str] = None
    calibration_path: Optional[str] = None
    debug_reconstruction: bool = True
    output_dir: str = "outputs/reconstruction_job"
    cache_dir: Optional[str] = None
    enable_cache: bool = True
    device: str = "auto"
    
    # Preset parameters
    preset: QualityPreset = field(default_factory=lambda: PRESETS["balanced"])
    
    # Learned adapter choice
    learned_adapter: str = "vggt"  # "vggt", "cut3r", "mast3r", "slam3r", "mvs_fallback"
    
    # Camera defaults if calibration missing
    default_fov_deg: float = 80.0
    known_focal_length_px: Optional[float] = None
    camera_model_type: str = "brown_conrady"  # "pinhole", "brown_conrady", "fisheye"
    camera_to_gps_lever_arm: tuple[float, float, float] = (0.0, 0.0, -0.1)  # (dx, dy, dz) meters
    
    # Trajectory optimization
    gps_weight: float = 10.0
    visual_weight: float = 1.0
    smoothness_weight: float = 2.0
    huber_delta: float = 2.0
    max_optimizer_iters: int = 50
    
    # Loop closure
    enable_loop_closure: bool = True
    loop_gps_dist_threshold_m: float = 15.0
    loop_min_frame_gap: int = 30
    loop_inlier_threshold: int = 35
    
    # Metric World & Surfels
    surfel_search_radius_m: float = 0.3
    surfel_merge_dist_m: float = 0.08
    surfel_normal_angle_deg: float = 35.0
    contradiction_loss_rate: float = 0.25
    
    # Evidence & Validation
    multiview_min_supporting_views: int = 2
    max_reprojection_error_px: float = 3.5
    z_buffer_depth_tolerance_m: float = 0.15
    
    # Structural Completion
    plane_ransac_dist_thresh_m: float = 0.06
    plane_min_inliers: int = 50
    max_structural_gap_m: float = 1.5
    
    # Generative Completion
    generative_candidates: int = 3
    generative_depth_consistency_tol_m: float = 0.25
    
    # Lens rectification: removes the calibrated distortion before tracking/SfM/stereo.
    # Without this a k1 of -0.28 displaces the image corners by hundreds of pixels and
    # every downstream pinhole assumption is violated.
    enable_undistortion: bool = True

    # Pose estimation. Incremental visual SfM solves the rotations that telemetry
    # cannot supply; GPS is then used only for metric scale and georeferencing.
    use_incremental_sfm: bool = True
    sfm_min_track_len: int = 3
    sfm_max_reproj_px: float = 2.0

    # Per-pointmap ICP against the partially built world drags geometry once the
    # poses are already globally consistent, so it is off by default.
    enable_pointmap_icp: bool = False

    # Texture & Meshing
    meshing_algorithm: str = "tsdf"  # "tsdf", "poisson", "ball_pivoting"
    texture_blending: str = "multiband"  # "multiband", "weighted_average", "best_view"
    texture_projective: bool = True
    texture_max_views_per_vertex: int = 6
    # Texture from the original frames, not the tracking proxies. Unlike the MVS
    # working resolution -- where more pixels made matching worse -- this side has no
    # matching in it: the geometry is already fixed and each face is only being
    # sampled, so a 1920 px source carries half again the texel detail of a 1280 px
    # proxy with no failure mode to trade against. Costs one extra full-res decode
    # per contributing view, in a stage that is already I/O bound.
    texture_full_resolution: bool = True
    mesh_depth_trunc_m: float = 150.0
    mesh_ground_align: bool = True
    target_mesh_faces: int = 250000
    include_walls: bool = True
    export_geospatial: bool = True
    ortho_gsd_m: float = 0.05
    
    # Quality Gates
    max_trajectory_drift_m: float = 2.5
    min_geometry_support_ratio: float = 0.65
    max_mean_reproj_error_px: float = 3.0
    min_mesh_face_count: int = 200

    def __post_init__(self):
        if self.quality.lower() in PRESETS:
            self.preset = PRESETS[self.quality.lower()]
        if self.cache_dir is None:
            self.cache_dir = str(Path(self.output_dir) / ".cache")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_name": self.job_name,
            "quality": self.quality,
            "video_path": self.video_path,
            "telemetry_path": self.telemetry_path,
            "output_dir": self.output_dir,
            "cache_dir": self.cache_dir,
            "enable_cache": self.enable_cache,
            "device": self.device,
            "learned_adapter": self.learned_adapter,
            "default_fov_deg": self.default_fov_deg,
            "preset": {
                "name": self.preset.name,
                "proxy_max_dim": self.preset.proxy_max_dim,
                "tracking_step": self.preset.tracking_step,
                "min_keyframe_parallax_deg": self.preset.min_keyframe_parallax_deg,
                "window_size": self.preset.window_size,
                "window_overlap": self.preset.window_overlap,
                "voxel_size_m": self.preset.voxel_size_m,
                "poisson_depth": self.preset.poisson_depth,
                "texture_resolution": self.preset.texture_resolution,
                "max_features": self.preset.max_features,
                "mvs_max_dim": self.preset.mvs_max_dim,
                "mvs_num_planes": self.preset.mvs_num_planes,
                "mvs_num_src_views": self.preset.mvs_num_src_views,
                "mvs_levels": self.preset.mvs_levels,
                "tsdf_voxel_m": self.preset.tsdf_voxel_m,
            },
            "enable_undistortion": self.enable_undistortion,
            "use_incremental_sfm": self.use_incremental_sfm,
            "enable_pointmap_icp": self.enable_pointmap_icp,
            "meshing_algorithm": self.meshing_algorithm,
            "mesh_smooth_iterations": self.preset.mesh_smooth_iterations
        }
