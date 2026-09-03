"""
Master Pipeline Orchestrator for SinglePass3D.
Executes all 25 implementation stages in the exact order specified by the architecture:
 1. project/config/logging
 2. video indexing
 3. telemetry/GPS
 4. camera calibration
 5. frame quality
 6. visual tracking
 7. GPS trajectory fusion
 8. adaptive keyframes
 9. classical SfM
 10. learned reconstruction adapter
 11. overlapping windows
 12. persistent world
 13. local-to-global registration
 14. confidence fusion
 15. global optimization
 16. loop closure
 17. multi-view validation
 18. semantics/dynamics
 19. high-resolution refinement
 20. structural completion
 21. generative completion
 22. texture
 23. mesh
 24. QA
 25. export
"""

from __future__ import annotations
from pathlib import Path
import json
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from singlepass3d.completion.generative_completion import GenerativeCompleter
from singlepass3d.completion.structural_completion import StructuralCompleter
from singlepass3d.completion.unknown_surface_model import UnknownSurfaceModeler
from singlepass3d.config.pipeline_config import SinglePass3DConfig
from singlepass3d.core.cache import PipelineCache
from singlepass3d.core.logging import SinglePass3DLogger, get_logger
from singlepass3d.core.types import Pose3D, Trajectory, WorldElement
from singlepass3d.evidence.confidence_engine import ConfidenceEngine
from singlepass3d.evidence.hr_refinement import HighResolutionRefiner
from singlepass3d.evidence.multi_view_validator import MultiViewValidator
from singlepass3d.evidence.semantics_dynamics import SemanticDynamicsFilter
from singlepass3d.geometry.classical_sfm import ClassicalSfMVerifier
from singlepass3d.geometry.keyframe_selector import KeyframeSelector
from singlepass3d.geometry.learned_adapters import get_adapter
from singlepass3d.geometry.trajectory_fusion import TrajectoryOptimizer
from singlepass3d.geometry.visual_tracker import VisualTracker
from singlepass3d.geometry.window_manager import WindowManager
from singlepass3d.metric_world.global_optimizer import GlobalRefinementPass
from singlepass3d.metric_world.local_registration import LocalRegistrationEngine
from singlepass3d.metric_world.loop_closure import LoopClosureDetector
from singlepass3d.metric_world.persistent_world import PersistentWorld
from singlepass3d.output.diagnostics_exporter import DiagnosticsExporter
from singlepass3d.output.exporter import ReconstructionExporter
from singlepass3d.output.mesh_generator import MeshGenerator
from singlepass3d.output.quality_assurance import QualityAssuranceAuditor
from singlepass3d.output.texture_synthesizer import TextureSynthesizer
from singlepass3d.sensor.camera_model import CameraModel
from singlepass3d.sensor.frame_quality import FrameQualityAnalyzer
from singlepass3d.sensor.telemetry_parser import TelemetryParser
from singlepass3d.sensor.video_indexer import VideoIndexer


class _CachedDepthFrame:
    """
    Disk-backed stand-in for a PointMapResult carrying only what TSDF fusion needs.

    A full-flight run produces hundreds of dense depth maps; holding them all in RAM
    costs several gigabytes, so each is compressed to disk and re-read on attribute
    access. Volumetric fusion touches every frame exactly once, so only one frame is
    resident at a time.
    """
    __slots__ = ("frame_id", "camera_pose", "_path", "_cache")

    def __init__(self, path: Path, frame_id: int, camera_pose: Optional[Pose3D]):
        self._path = Path(path)
        self.frame_id = int(frame_id)
        self.camera_pose = camera_pose
        self._cache: Optional[Dict[str, np.ndarray]] = None

    def _load(self) -> Dict[str, np.ndarray]:
        if self._cache is None:
            with np.load(self._path) as z:
                self._cache = {k: z[k] for k in z.files}
        return self._cache

    def release(self) -> None:
        self._cache = None

    @property
    def depth(self) -> np.ndarray:
        return self._load()["depth"]

    @property
    def colors(self) -> np.ndarray:
        return self._load()["colors"]

    @property
    def K(self) -> np.ndarray:
        return self._load()["K"]

    @property
    def mask(self) -> np.ndarray:
        return self._load()["mask"]

    @property
    def confidences(self) -> np.ndarray:
        return self._load()["confidences"]

    @property
    def points(self) -> None:
        return None

    @property
    def normals(self) -> None:
        return None


def _cache_depth_frame(cache_dir: Path, pmap, max_dim: int = 1024) -> Optional[_CachedDepthFrame]:
    """
    Persists one dense depth map for the later volumetric fusion stage.

    Returns None when the pointmap carries no usable depth (no pose, no depth map,
    or an entirely invalid mask), so callers can simply skip it.
    """
    depth = getattr(pmap, "depth", None)
    K = getattr(pmap, "K", None)
    if depth is None or K is None or pmap.camera_pose is None:
        return None

    depth = np.asarray(depth, dtype=np.float32)
    mask = np.asarray(pmap.mask, dtype=bool)
    if mask.shape != depth.shape:
        mask = np.ones_like(depth, dtype=bool)
    if not np.any(mask & (depth > 0.0)):
        return None

    colors = np.asarray(pmap.colors)
    if colors.dtype != np.uint8:
        colors = np.clip(colors, 0, 255).astype(np.uint8)
    conf = np.asarray(pmap.confidences, dtype=np.float32)
    K = np.asarray(K, dtype=np.float64).copy()

    h, w = depth.shape[:2]
    scale = min(1.0, float(max_dim) / float(max(h, w)))
    if scale < 1.0:
        nw, nh = int(round(w * scale)), int(round(h * scale))
        # Nearest keeps depth discontinuities crisp; interpolating across an edge
        # invents surfaces that bridge a roof to the ground behind it.
        depth = cv2.resize(depth, (nw, nh), interpolation=cv2.INTER_NEAREST)
        mask = cv2.resize(mask.astype(np.uint8), (nw, nh), interpolation=cv2.INTER_NEAREST).astype(bool)
        conf = cv2.resize(conf, (nw, nh), interpolation=cv2.INTER_NEAREST)
        colors = cv2.resize(colors, (nw, nh), interpolation=cv2.INTER_AREA)
        sx, sy = nw / float(w), nh / float(h)
        K[0, 0] *= sx; K[0, 2] *= sx
        K[1, 1] *= sy; K[1, 2] *= sy

    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"depth_{int(pmap.frame_id):06d}.npz"
    np.savez_compressed(
        out, depth=depth, colors=colors, K=K, mask=mask, confidences=conf
    )
    return _CachedDepthFrame(out, pmap.frame_id, pmap.camera_pose)


class SinglePass3DPipeline:
    """
    Continuous multi-view drone-video-to-3D reconstruction system.
    """
    def __init__(self, config: SinglePass3DConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = SinglePass3DLogger(
            name="SinglePass3D",
            log_file=self.output_dir / "pipeline.log"
        )
        self.cache = PipelineCache(
            cache_dir=config.cache_dir or (self.output_dir / ".cache"),
            enabled=config.enable_cache
        )

    def _attach_barometric_altitude(self, telemetry: TelemetryParser) -> None:
        """
        Looks for a barometric pressure log beside the telemetry file and fuses it.

        The problem statement lists barometric altitude as an available input, and it
        is the one channel that pins height down when the GNSS fix cannot: pressure
        tracks a climb to a few centimetres regardless of satellite geometry.
        """
        src = self.config.telemetry_path
        if not src:
            return
        folder = Path(src).parent
        for name in ("BarometricPressure.csv", "barometric_pressure.csv",
                     "barometer.csv", "baro.csv", "BarometricPressure.CSV"):
            cand = folder / name
            if cand.exists():
                try:
                    telemetry.attach_barometric_altitude(cand)
                except Exception as exc:
                    self.logger.warning(f"Barometric log at {cand.name} unusable ({exc}).")
                return

    def run(self, max_frames: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes the entire 25-stage continuous reconstruction pipeline.
        """
        self.logger.info(f"Starting SinglePass3D Pipeline [Preset: {self.config.preset.name}]")
        
        # ----------------------------------------------------
        # STAGE 1: Project / Config / Logging
        # ----------------------------------------------------
        self.logger.start_stage(1, "Project / Config / Logging", "Initialize workspace and diagnostics")
        self.logger.info(f"Configuration: {self.config.to_dict()}")
        self.logger.end_stage()

        diag_exporter = DiagnosticsExporter(self.output_dir / "diagnostics") if self.config.debug_reconstruction else None

        # ----------------------------------------------------
        # STAGE 2: Video Indexing
        # ----------------------------------------------------
        self.logger.start_stage(2, "Video Indexing", "Decode full sequence and build proxy store")
        if not self.config.video_path:
            raise ValueError("video_path must be specified in config.")
            
        indexer = VideoIndexer(
            video_path=self.config.video_path,
            work_dir=self.output_dir,
            proxy_max_dim=self.config.preset.proxy_max_dim,
            tracking_step=self.config.preset.tracking_step
        )
        frame_metadata_list = indexer.index_video(max_frames=max_frames)
        if diag_exporter:
            diag_exporter.export_01_frames(indexer)
        self.logger.end_stage(details={"total_frames": len(frame_metadata_list)})

        # ----------------------------------------------------
        # STAGE 3: Telemetry / GPS
        # ----------------------------------------------------
        self.logger.start_stage(3, "Telemetry / GPS", "Parse flight log and convert WGS84 to local ENU")
        telemetry = TelemetryParser(self.config.telemetry_path)
        telemetry_points = telemetry.parse()
        if telemetry_points:
            self._attach_barometric_altitude(telemetry)
        # An explicit image number in the log beats any inferred clock offset, so it is
        # tried first and correlation is only the fallback.
        if not telemetry.align_to_image_sequence(indexer):
            video_timestamps = [m.timestamp for m in frame_metadata_list]
            telemetry.estimate_video_time_offset(video_timestamps)
        if diag_exporter:
            diag_exporter.export_05_gps_trajectory(telemetry)
        self.logger.end_stage(details={"telemetry_records": len(telemetry_points)})

        # ----------------------------------------------------
        # STAGE 4: Camera Calibration
        # ----------------------------------------------------
        self.logger.start_stage(4, "Camera Calibration", "Estimate intrinsics, distortion, and lever arm")
        # Check for explicit calibration or auto-detect calibration_data.npz
        calib_file = None
        if self.config.calibration_path and Path(self.config.calibration_path).exists():
            calib_file = Path(self.config.calibration_path)
        elif self.config.video_path:
            vpath = Path(self.config.video_path)
            candidate_npz1 = vpath.parent / "calibration_data.npz"
            candidate_npz2 = vpath.parent.parent / "calibration_data.npz"
            if candidate_npz1.exists():
                calib_file = candidate_npz1
            elif candidate_npz2.exists():
                calib_file = candidate_npz2

        if calib_file is not None:
            self.logger.info(f"Loading calibrated camera intrinsics from: {calib_file}")
            camera = CameraModel.from_calibration_file(
                calib_path=calib_file,
                width=indexer.original_width,
                height=indexer.original_height,
                model_type=self.config.camera_model_type,
                lever_arm_xyz=self.config.camera_to_gps_lever_arm
            )
        else:
            camera = CameraModel.create_default(
                width=indexer.original_width,
                height=indexer.original_height,
                fov_deg=self.config.default_fov_deg,
                known_focal_length_px=self.config.known_focal_length_px,
                model_type=self.config.camera_model_type,
                lever_arm_xyz=self.config.camera_to_gps_lever_arm
            )
        # Lens rectification. The AGZ lens has k1 = -0.28, which displaces the image
        # corners by roughly 230 px; every pinhole assumption downstream (tracking,
        # SfM, plane-sweep homographies, projective texturing) is violated until the
        # distortion is removed. From here on `camera` is the ideal pinhole model and
        # every frame the indexer hands out has been remapped into it.
        camera_source = camera
        if self.config.enable_undistortion and not np.allclose(camera.data.distortion, 0):
            camera = camera.undistorted_model()
            indexer.set_undistortion(camera_source, camera)
            self.logger.info(
                f"Lens rectification active: {camera_source.data.model_type} -> pinhole "
                f"(k1={float(camera_source.data.distortion[0]):.4f})"
            )
        self.logger.end_stage(details=camera.data.to_dict())

        # ----------------------------------------------------
        # STAGE 5: Frame Quality
        # ----------------------------------------------------
        self.logger.start_stage(5, "Frame Quality", "Evaluate sharpness, blur, and motion density")
        quality_analyzer = FrameQualityAnalyzer(indexer=indexer, max_features=self.config.preset.max_features)
        quality_analyzer.analyze_all_frames()
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 6: Visual Tracking
        # ----------------------------------------------------
        self.logger.start_stage(6, "Visual Tracking", "Track continuous features across video frames")
        tracker = VisualTracker(indexer=indexer, max_features=self.config.preset.max_features)
        tracking_fids = indexer.get_tracking_frame_ids()
        tracks = tracker.track_sequence(tracking_fids)
        if diag_exporter:
            diag_exporter.export_03_tracks(tracks)
        self.logger.end_stage(details={"valid_tracks": len(tracks)})

        # ----------------------------------------------------
        # STAGE 7: GPS Trajectory Fusion
        # ----------------------------------------------------
        self.logger.start_stage(7, "GPS Trajectory Fusion", "Solve GPS-constrained visual factor graph")
        traj_optimizer = TrajectoryOptimizer(
            camera=camera,
            gps_weight=self.config.gps_weight,
            visual_weight=self.config.visual_weight,
            smoothness_weight=self.config.smoothness_weight,
            huber_delta=self.config.huber_delta,
            max_iters=self.config.max_optimizer_iters
        )
        # Telemetry alone cannot orient the camera: this flight log carries position
        # but no attitude, so a GPS factor graph assigns every frame the same rotation.
        # Incremental visual SfM solves the rotations from the imagery and is then
        # aligned to GPS for metric scale and georeferencing, which supersedes the
        # factor graph entirely -- so the factor graph is only solved if SfM cannot
        # deliver. On a few hundred frames that ordering saves minutes of dead work.
        initial_trajectory = None
        sfm_landmarks: np.ndarray = np.empty((0, 3), dtype=np.float64)
        sfm_stats: Dict[str, Any] = {}
        if self.config.use_incremental_sfm:
            try:
                from singlepass3d.geometry.incremental_sfm import IncrementalSfM

                telemetry_enu: Dict[int, np.ndarray] = {}
                gps_sigma: Dict[int, float] = {}
                gps_sigma_up: Dict[int, float] = {}
                for fid in tracking_fids:
                    meta = indexer.frame_index.get(fid)
                    tele = telemetry.get_telemetry_at(meta.timestamp) if meta is not None else None
                    if tele is not None:
                        telemetry_enu[fid] = np.array(
                            [tele.enu_x, tele.enu_y, tele.enu_z], dtype=np.float64
                        )
                        gps_sigma[fid] = float(max(0.1, tele.uncertainty))
                        gps_sigma_up[fid] = float(
                            max(0.05, tele.vertical_uncertainty or tele.uncertainty * 1.6)
                        )

                # Tracks are measured on the proxy frames, so SfM needs the
                # intrinsics at that resolution rather than the full-res model.
                probe = indexer.get_frame_image(tracking_fids[0], full_resolution=False)
                sfm_camera = camera.scale_to_resolution(probe.shape[1], probe.shape[0])
                stamps = {
                    fid: float(indexer.frame_index[fid].timestamp)
                    for fid in tracking_fids if fid in indexer.frame_index
                }

                sfm = IncrementalSfM(
                    camera=sfm_camera,
                    min_track_len=self.config.sfm_min_track_len,
                    max_reproj_px=self.config.sfm_max_reproj_px,
                )
                sfm_traj, sfm_landmarks, sfm_stats = sfm.reconstruct(
                    frame_ids=tracking_fids,
                    tracks=tracks,
                    telemetry_enu=telemetry_enu or None,
                    gps_sigma=gps_sigma or None,
                    gps_sigma_up=gps_sigma_up or None,
                    timestamps=stamps,
                )
                if sfm_traj is not None and len(sfm_traj.poses) >= max(2, len(tracking_fids) // 4):
                    initial_trajectory = sfm_traj
                    self.logger.info(f"Incremental SfM trajectory adopted: {sfm_stats}")
                else:
                    self.logger.warning(
                        "Incremental SfM registered too few frames; falling back to the "
                        "GPS-constrained factor graph."
                    )
            except Exception as exc:
                self.logger.warning(
                    f"Incremental SfM unavailable or failed ({exc}); falling back to the "
                    "GPS-constrained factor graph."
                )

        if initial_trajectory is None:
            initial_trajectory = traj_optimizer.optimize_trajectory(
                frame_ids=tracking_fids,
                indexer=indexer,
                telemetry=telemetry,
                tracks=tracks,
            )

        if diag_exporter:
            diag_exporter.export_04_camera_trajectory(initial_trajectory)
        self.logger.end_stage(details={"optimized_poses": len(initial_trajectory.poses)})

        # ----------------------------------------------------
        # STAGE 8: Adaptive Keyframes
        # ----------------------------------------------------
        self.logger.start_stage(8, "Adaptive Keyframes", "Select reconstruction frames by parallax and baseline")
        keyframe_selector = KeyframeSelector(
            indexer=indexer,
            min_parallax_deg=self.config.preset.min_keyframe_parallax_deg,
            max_frame_gap=self.config.preset.keyframe_max_frame_gap,
        )
        keyframe_ids = keyframe_selector.select_reconstruction_keyframes(
            trajectory=initial_trajectory,
            candidate_frame_ids=tracking_fids
        )
        if diag_exporter:
            diag_exporter.export_02_selected_frames(indexer, keyframe_ids)
        self.logger.end_stage(details={"reconstruction_keyframes": len(keyframe_ids)})

        # ----------------------------------------------------
        # STAGE 9: Classical SfM Independent Verification
        # ----------------------------------------------------
        self.logger.start_stage(9, "Classical SfM", "Independent triangulation and reprojection verification")
        classical_verifier = ClassicalSfMVerifier(camera=camera, work_dir=self.output_dir)
        classical_landmarks = classical_verifier.run_classical_verification(
            keyframe_ids=keyframe_ids,
            indexer=indexer,
            tracks=tracks,
            trajectory=initial_trajectory
        )
        if diag_exporter:
            diag_exporter.export_06_sparse_cloud(classical_landmarks)
        self.logger.end_stage(details={"triangulated_landmarks": len(classical_landmarks)})

        # ----------------------------------------------------
        # STAGE 10: Learned Reconstruction Adapter
        # ----------------------------------------------------
        self.logger.start_stage(10, "Learned Reconstruction Adapter", f"Initialize {self.config.learned_adapter.upper()} adapter")
        preset = self.config.preset
        adapter = get_adapter(
            self.config.learned_adapter,
            device=self.config.device,
            mvs_num_planes=preset.mvs_num_planes,
            mvs_num_src_views=preset.mvs_num_src_views,
            mvs_max_dim=preset.mvs_max_dim,
            mvs_zncc_win=preset.mvs_zncc_win,
            mvs_geo_consistency_views=preset.mvs_geo_consistency_views,
            mvs_min_confidence=preset.mvs_min_confidence,
            mvs_levels=preset.mvs_levels,
        )

        # Seed the stereo depth range from the sparse structure rather than from a
        # hardcoded altitude guess.
        scene_prior = sfm_landmarks if len(sfm_landmarks) else np.asarray(classical_landmarks, dtype=np.float64)
        prior_setter = getattr(adapter, "set_scene_prior", None)
        if prior_setter is not None and len(scene_prior):
            prior_setter(np.asarray(scene_prior, dtype=np.float64).reshape(-1, 3))
            self.logger.info(f"Dense stereo depth range seeded from {len(scene_prior)} sparse points.")
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 11: Overlapping Windows
        # ----------------------------------------------------
        self.logger.start_stage(11, "Overlapping Windows", "Partition keyframes into overlapping clips")
        window_mgr = WindowManager(
            window_size=self.config.preset.window_size,
            window_overlap=self.config.preset.window_overlap
        )
        windows = window_mgr.create_overlapping_windows(keyframe_ids=keyframe_ids, indexer=indexer)
        self.logger.end_stage(details={"total_windows": len(windows)})

        # ----------------------------------------------------
        # STAGE 12: Persistent World State Initialization
        # ----------------------------------------------------
        self.logger.start_stage(12, "Persistent World", "Initialize spatial surface element (surfel) store")
        world = PersistentWorld(
            voxel_size_m=self.config.preset.voxel_size_m,
            merge_dist_m=self.config.surfel_merge_dist_m,
            normal_angle_deg=self.config.surfel_normal_angle_deg,
            contradiction_loss_rate=self.config.contradiction_loss_rate
        )
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 13 & 14: Local-to-Global Registration and Confidence Fusion across windows
        # ----------------------------------------------------
        self.logger.start_stage(13, "Local-to-Global Registration", "Iteratively register and fuse window pointmaps")
        
        # Dense depth maps are the raw material for volumetric fusion in stage 23.
        # They are streamed to disk so a full flight does not have to fit in RAM.
        depth_cache_dir = self.output_dir / "depth_cache"
        depth_frames: List[_CachedDepthFrame] = []
        cached_fids = set()
        T_reg = np.eye(4, dtype=np.float64)

        # A window is a memory and streaming boundary, not a geometric one. Depth
        # precision scales with the baseline between the views being matched, so an
        # engine that can only see inside its own window is limited to whatever the
        # aircraft happened to fly in those few seconds -- tens of centimetres on a
        # slow pass, against metres available over the flight. Engines that advertise
        # `supports_source_pool` are handed every posed frame plus a lazy image
        # reader, and choose source views on baseline instead of adjacency.
        source_pool: List[Tuple[int, Optional[Pose3D]]] = []
        if getattr(adapter, "supports_source_pool", False):
            seen_pool = set()
            for win in windows:
                for fid in win.frame_ids:
                    if fid in seen_pool:
                        continue
                    ps = initial_trajectory.get_pose(fid)
                    if ps is None:
                        continue
                    seen_pool.add(fid)
                    source_pool.append((int(fid), ps))
            if source_pool:
                span = np.ptp(np.array([p.t_wc for _, p in source_pool]), axis=0)
                self.logger.info(
                    f"Source view pool: {len(source_pool)} posed frames spanning "
                    f"{span[0]:.1f} x {span[1]:.1f} x {span[2]:.1f} m, available to every window."
                )

        for win in windows:
            self.logger.info(f"Processing Reconstruction Window {win.window_id + 1}/{len(windows)} ({len(win.frame_ids)} frames)...")
            
            # Load images and initial poses for window frames
            win_images = [indexer.get_frame_image(fid, full_resolution=False) for fid in win.frame_ids]
            win_poses = [initial_trajectory.get_pose(fid) for fid in win.frame_ids]
            
            # Execute learned reconstruction adapter
            recon_kwargs = {}
            if source_pool:
                recon_kwargs["source_pool"] = source_pool
                recon_kwargs["image_provider"] = (
                    lambda fid: indexer.get_frame_image(fid, full_resolution=False)
                )
            pointmaps = adapter.reconstruct_window(
                frames=win_images,
                frame_ids=win.frame_ids,
                camera=camera,
                initial_poses=win_poses,
                **recon_kwargs
            )
            
            if diag_exporter:
                diag_exporter.export_07_local_pointmaps(pointmaps, win.window_id)
            
            # Register and fuse each pointmap into persistent world
            for pmap in pointmaps:
                # Local-to-global ICP. Once the poses come from a globally consistent
                # SfM solution this only drags geometry around, so it is opt-in.
                if self.config.enable_pointmap_icp:
                    T_reg, inlier_rmse, success = world.registration_engine.register_pointmap_to_world(
                        pointmap_res=pmap,
                        world_store=world.store
                    )
                else:
                    T_reg = np.eye(4, dtype=np.float64)
                
                # STAGE 14: Confidence fusion
                world.integrate_pointmap(pointmap_res=pmap, registered_T=T_reg)

                # Overlapping windows revisit frames; keep the first dense depth map.
                if pmap.frame_id not in cached_fids:
                    cached = _cache_depth_frame(depth_cache_dir, pmap)
                    if cached is not None:
                        depth_frames.append(cached)
                        cached_fids.add(pmap.frame_id)
                
            if diag_exporter:
                diag_exporter.export_08_registered_windows(pointmaps, win.window_id, T_reg)
                
        # Prune spurious hypotheses
        world.prune_unsupported_hypotheses(min_confidence=0.20)
        if diag_exporter:
            diag_exporter.export_09_fused_world(world)
        self.logger.end_stage(details={
            "world_surfels": len(world.store),
            "dense_depth_frames": len(depth_frames),
        })

        # ----------------------------------------------------
        # STAGE 15: Global Optimization
        # ----------------------------------------------------
        self.logger.start_stage(15, "Global Optimization", "Full flight offline trajectory and surfel refinement pass")
        global_refiner = GlobalRefinementPass(
            camera=camera,
            trajectory_optimizer=traj_optimizer,
            max_iters=self.config.max_optimizer_iters
        )
        # The trajectory optimizer holds its landmarks fixed and weights raw GPS at
        # 10x the visual term. That is the right behaviour when poses came from
        # telemetry, but it would drag a bundle-adjusted, GPS-aligned SfM solution
        # back toward 13 m-accurate GPS positions, so it is skipped in that case.
        sfm_trusted = bool(sfm_stats) and initial_trajectory is not None and len(sfm_landmarks) > 0
        if sfm_trusted:
            self.logger.info(
                "Skipping GPS-dominated global re-fit: the SfM trajectory is already "
                "bundle-adjusted and GPS-aligned."
            )
            refined_trajectory = initial_trajectory
        else:
            refined_trajectory = global_refiner.run_global_refinement(
                trajectory=initial_trajectory,
                world=world,
                indexer=indexer,
                telemetry=telemetry,
                tracks=tracks
            )
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 16: Loop Closure
        # ----------------------------------------------------
        self.logger.start_stage(16, "Loop Closure", "Detect revisits and correct global drift")
        if self.config.enable_loop_closure:
            loop_detector = LoopClosureDetector(
                camera=camera,
                min_frame_gap=self.config.loop_min_frame_gap,
                gps_dist_threshold_m=self.config.loop_gps_dist_threshold_m,
                min_inliers=self.config.loop_inlier_threshold
            )
            loop_constraints = loop_detector.detect_loop_closures(
                keyframe_ids=keyframe_ids,
                indexer=indexer,
                trajectory=refined_trajectory
            )
            if loop_constraints and not sfm_trusted:
                refined_trajectory = global_refiner.run_global_refinement(
                    trajectory=refined_trajectory,
                    world=world,
                    indexer=indexer,
                    telemetry=telemetry,
                    tracks=tracks,
                    loop_constraints=loop_constraints
                )
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 17: Multi-View Validation
        # ----------------------------------------------------
        self.logger.start_stage(17, "Multi-View Validation", "Rigorous multi-view reprojection quality testing")
        validator = MultiViewValidator(
            camera=camera,
            max_reprojection_error_px=self.config.max_reprojection_error_px
        )
        validation_stats = validator.validate_world(
            world=world,
            trajectory=refined_trajectory,
            indexer=indexer,
            sample_keyframe_ids=keyframe_ids
        )
        
        # Update composite confidence ratings
        confidence_engine = ConfidenceEngine()
        confidence_engine.evaluate_world_confidence(
            world=world,
            trajectory=refined_trajectory,
            indexer=indexer
        )
        if diag_exporter:
            diag_exporter.export_11_validated_world(world)
        self.logger.end_stage(details=validation_stats)

        # ----------------------------------------------------
        # STAGE 18: Semantics / Dynamics
        # ----------------------------------------------------
        self.logger.start_stage(18, "Semantics / Dynamics", "Classify 10 semantic classes and filter dynamics")
        semantic_filter = SemanticDynamicsFilter()
        semantic_stats = semantic_filter.process_world(world=world)
        if diag_exporter:
            diag_exporter.export_10_filtered_world(world)
        self.logger.end_stage(details=semantic_stats)

        # ----------------------------------------------------
        # STAGE 19: High-Resolution Refinement
        # ----------------------------------------------------
        self.logger.start_stage(19, "High-Resolution Refinement", "Targeted full-res crop refinement on facades/roofs")
        if self.config.preset.high_res_refinement:
            hr_refiner = HighResolutionRefiner(camera=camera)
            hr_refiner.refine_structural_regions(
                world=world,
                trajectory=refined_trajectory,
                indexer=indexer
            )
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 20: Structural Completion
        # ----------------------------------------------------
        self.logger.start_stage(20, "Structural Completion", "Architectural planar regularization and gap filling")
        if self.config.preset.structural_completion:
            structural_completer = StructuralCompleter(
                plane_dist_thresh_m=self.config.plane_ransac_dist_thresh_m,
                min_plane_inliers=self.config.plane_min_inliers,
                max_gap_size_m=self.config.max_structural_gap_m
            )
            structural_completer.apply_structural_completion(world=world)
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 21: Generative Completion
        # ----------------------------------------------------
        self.logger.start_stage(21, "Generative Completion", "Constrained completion strictly on UNKNOWN voids")
        unknown_modeler = UnknownSurfaceModeler(camera=camera)
        unknown_modeler.classify_visibility_and_unseen_regions(world=world, trajectory=refined_trajectory)
        
        if self.config.preset.generative_completion:
            generative_completer = GenerativeCompleter(
                camera=camera,
                candidate_count=self.config.generative_candidates
            )
            generative_completer.generate_and_validate_completions(
                world=world,
                trajectory=refined_trajectory
            )
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 22: Texture Synthesis
        # ----------------------------------------------------
        self.logger.start_stage(22, "Texture Synthesis", "Multi-view texture blending and UV atlas generation")
        tex_synthesizer = TextureSynthesizer(
            camera=camera,
            texture_size=self.config.preset.texture_resolution
        )
        self.logger.end_stage()

        # ----------------------------------------------------
        # STAGE 23: Mesh Generation
        # ----------------------------------------------------
        self.logger.start_stage(23, "Mesh Generation", "Surface reconstruction and manifold topological filtering")
        mesh_gen = MeshGenerator(
            algorithm=self.config.meshing_algorithm,
            poisson_depth=self.config.preset.poisson_depth,
            tsdf_voxel_m=self.config.preset.tsdf_voxel_m,
            tsdf_sdf_trunc_mult=self.config.preset.tsdf_sdf_trunc_mult,
            smooth_iterations=self.config.preset.mesh_smooth_iterations,
            depth_trunc_m=self.config.mesh_depth_trunc_m,
            ground_align=self.config.mesh_ground_align,
        )

        # Volumetric fusion of the dense depth maps resolves far more detail than
        # Poisson over voxel-averaged surfels, so it is the primary path. Re-point
        # each cached depth frame at the final refined pose before fusing.
        final_mesh = None
        if self.config.meshing_algorithm.lower() == "tsdf" and depth_frames:
            for cached in depth_frames:
                refined_pose = refined_trajectory.get_pose(cached.frame_id)
                if refined_pose is not None:
                    cached.camera_pose = refined_pose
            try:
                final_mesh = mesh_gen.generate_mesh_from_depths(depth_frames, world=world)
            except Exception as exc:
                self.logger.warning(f"TSDF fusion failed ({exc}); falling back to surfel meshing.")
                final_mesh = None
            finally:
                for cached in depth_frames:
                    cached.release()

        if final_mesh is None or len(final_mesh.faces) == 0:
            final_mesh = mesh_gen.generate_mesh(world=world)

        # Color mesh vertices. Projective multi-view texturing samples the rectified
        # imagery directly, so its sharpness is not capped by the surfel grid.
        vertex_colors = None
        if self.config.texture_projective and len(refined_trajectory.poses) > 0:
            try:
                vertex_colors = tex_synthesizer.synthesize_vertex_colors_projective(
                    vertices=np.asarray(final_mesh.vertices, dtype=np.float64),
                    normals=np.asarray(final_mesh.vertex_normals, dtype=np.float64),
                    trajectory=refined_trajectory,
                    indexer=indexer,
                    faces=np.asarray(final_mesh.faces),
                    max_views_per_vertex=self.config.texture_max_views_per_vertex,
                    full_resolution=self.config.texture_full_resolution,
                    world_from_mesh=mesh_gen.world_from_mesh,
                )
            except Exception as exc:
                self.logger.warning(f"Projective texturing failed ({exc}); using surfel colour transfer.")
                vertex_colors = None

        if vertex_colors is None:
            vertex_colors = tex_synthesizer.synthesize_vertex_and_face_colors(
                vertices=final_mesh.vertices,
                normals=final_mesh.vertex_normals,
                world=world,
                trajectory=refined_trajectory,
                indexer=indexer
            )
        try:
            final_mesh.visual.vertex_colors = vertex_colors
        except Exception:
            pass
        # A voxel-spaced vertex palette throws away most of what the frames resolved, so
        # the exported model carries a baked atlas instead wherever one can be built.
        textured_mesh = None
        if self.config.texture_projective and len(refined_trajectory.poses) > 0:
            try:
                textured_mesh = tex_synthesizer.bake_uv_atlas(
                    mesh=final_mesh,
                    trajectory=refined_trajectory,
                    indexer=indexer,
                    world_from_mesh=mesh_gen.world_from_mesh,
                    full_resolution=self.config.texture_full_resolution,
                )
            except Exception as exc:
                self.logger.warning(f"UV atlas baking failed ({exc}); exporting vertex colour only.")
                textured_mesh = None
        self.logger.end_stage(details={
            "vertices": len(final_mesh.vertices),
            "faces": len(final_mesh.faces),
            "atlas_px": tex_synthesizer.last_atlas_px,
            "atlas_texel_cm": round(tex_synthesizer.last_atlas_texel_m * 100.0, 2),
        })

        # ----------------------------------------------------
        # STAGE 24: Quality Assurance (QA)
        # ----------------------------------------------------
        self.logger.start_stage(24, "Quality Assurance", "Evaluate trajectory, geometry, mesh, and texture QA gates")
        auditor = QualityAssuranceAuditor(
            max_trajectory_drift_m=self.config.max_trajectory_drift_m,
            min_geometry_support_ratio=self.config.min_geometry_support_ratio,
            max_mean_reproj_error_px=self.config.max_mean_reproj_error_px,
            min_mesh_faces=self.config.min_mesh_face_count
        )
        qa_report = auditor.audit_reconstruction(
            world=world,
            trajectory=refined_trajectory,
            mesh=final_mesh,
            telemetry=telemetry,
            texture_coverage=(
                tex_synthesizer.last_direct_coverage
                if tex_synthesizer.last_views_used > 0 else None
            ),
            texture_views=tex_synthesizer.last_views_used
        )
        self.logger.end_stage(details={"qa_status": qa_report["quality_status"]})

        # ----------------------------------------------------
        # STAGE 25: Output Export
        # ----------------------------------------------------
        self.logger.start_stage(25, "Output Export", "Export GLB, PLY, OBJ, trajectory, cameras, world, report")
        exporter = ReconstructionExporter(output_dir=self.output_dir)
        exported_files = exporter.export_all(
            mesh=final_mesh,
            world=world,
            trajectory=refined_trajectory,
            camera=camera,
            qa_report=qa_report,
            custom_logger=self.logger,
            textured_mesh=textured_mesh
        )
        # The inferred building envelope ships as its own pair of files. Merging it
        # into model.* would put more inferred surface in the delivered mesh than the
        # flight measured, and would hide the facade that was actually observed behind
        # it; kept separate it can be viewed and measured for what it is.
        envelope = getattr(mesh_gen, "last_envelope", None)
        if envelope is not None and len(envelope.faces):
            for ext in ("ply", "glb"):
                try:
                    envelope.export(self.output_dir / f"model_envelope.{ext}")
                    exported_files.append(str(self.output_dir / f"model_envelope.{ext}"))
                except Exception as exc:
                    self.logger.debug(f"Envelope export ({ext}) skipped: {exc}")

        # The face tags do not survive PLY or GLB, so they ship beside the model.
        # Without this the delivered mesh is unusable for measurement: a surveyor
        # holding model.ply has no way to tell a triangle the flight observed from
        # one interpolated across a gap, and the whole point of separating them is
        # that the consumer gets to decide which to trust.
        inferred = (final_mesh.metadata or {}).get("inferred_faces")
        n_inf = int(len(inferred)) if inferred is not None else 0
        try:
            prov = {
                "delivered_mesh": "model.ply",
                "face_count": int(len(final_mesh.faces)),
                "measured_faces": int(len(final_mesh.faces)) - n_inf,
                "inferred_faces": n_inf,
                "inferred_area_m2": float((final_mesh.metadata or {}).get("inferred_area_m2", 0.0)),
                "inference_method": (
                    "planar interpolation across enclosed gaps in observed planes"
                    if n_inf else "none"
                ),
                "inferred_face_indices": (
                    np.asarray(inferred, dtype=np.int64).tolist() if n_inf else []
                ),
                "envelope_artifact": (
                    "model_envelope.ply" if envelope is not None and len(envelope.faces) else None
                ),
                "envelope_note": (
                    "Building envelope extruded from observed roof rims down to ground. "
                    "Not measured surface: the flight saw one facade and the roofs, so the "
                    "remaining walls are implied by them and nothing more. Kept out of the "
                    "delivered mesh and shipped separately so it can never be mistaken for "
                    "measurement."
                ),
            }
            with open(self.output_dir / "provenance.json", "w", encoding="utf-8") as fh:
                json.dump(prov, fh, indent=2)
            exported_files.append(str(self.output_dir / "provenance.json"))
        except Exception as exc:
            self.logger.debug(f"Provenance sidecar skipped: {exc}")

        if n_inf:
            self.logger.info(
                f"Delivered mesh: {len(final_mesh.faces) - n_inf} measured "
                f"triangles, {n_inf} inferred "
                f"({(final_mesh.metadata or {}).get('inferred_area_m2', 0.0):.1f} m2, "
                f"{100.0 * n_inf / max(1, len(final_mesh.faces)):.1f}%)."
            )

        if diag_exporter:
            diag_exporter.export_12_mesh(self.output_dir / "model.ply")
        self.logger.end_stage(details={"exported_count": len(exported_files)})

        self.logger.info("=======================================================")
        self.logger.info("SinglePass3D Continuous Reconstruction Pipeline COMPLETE!")
        self.logger.info(f"Output directory: {self.output_dir.resolve()}")
        self.logger.info(f"QA Status: {qa_report['quality_status']}")
        self.logger.info("=======================================================")

        return {
            "qa_report": qa_report,
            "exported_files": exported_files,
            "output_dir": str(self.output_dir.resolve())
        }
