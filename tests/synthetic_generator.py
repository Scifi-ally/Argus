"""
Synthetic Drone Flight and Video & Telemetry Generator for SinglePass3D Test Suite.
Generates multi-view video sequences and synchronized DJI SRT telemetry files
simulating various drone flight patterns, scenes, and challenges.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np


class SyntheticFlightGenerator:
    """
    Generates synthetic drone video frames and synchronized SRT telemetry files.
    """
    def __init__(self, width: int = 640, height: int = 480, fps: float = 30.0):
        self.width = width
        self.height = height
        self.fps = fps

    def generate_flight(
        self,
        flight_type: str = "forward",  # forward, lateral, orbit, altitude, long, gps_noise, motion_blur, low_texture, repeated, vegetation, vehicles, occlusion, loop_closure, unseen
        num_frames: int = 45,
        output_video_path: Optional[str | Path] = None,
        output_srt_path: Optional[str | Path] = None,
        ref_lat: float = 37.774900,
        ref_lon: float = -122.419400,
        ref_alt: float = 35.0
    ) -> Tuple[Path, Path]:
        """
        Creates synthetic MP4 and SRT files for the specified scenario.
        """
        video_p = Path(output_video_path or f"synthetic_{flight_type}.mp4")
        srt_p = Path(output_srt_path or f"synthetic_{flight_type}.srt")
        video_p.parent.mkdir(parents=True, exist_ok=True)
        srt_p.parent.mkdir(parents=True, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(str(video_p), fourcc, self.fps, (self.width, self.height))

        srt_lines: List[str] = []

        # Ground 3D landmarks (x, y, z, color_bgr)
        # Simulate building at center (0, 15, 0..8m) and terrain
        landmarks: List[Tuple[np.ndarray, Tuple[int, int, int]]] = []
        
        # Ground grid
        for gx in np.linspace(-20, 20, 15):
            for gy in np.linspace(-5, 45, 20):
                color = (34, 139, 34) if flight_type == "vegetation" else (100, 100, 100)
                landmarks.append((np.array([gx, gy, 0.0]), color))
                
        # Building box (x: -5..5, y: 15..25, z: 0..8)
        for bx in np.linspace(-4, 4, 8):
            for by in np.linspace(16, 24, 8):
                # Roof
                landmarks.append((np.array([bx, by, 6.0]), (80, 80, 200)))  # Reddish roof
                # Walls
                landmarks.append((np.array([bx, 16.0, 3.0]), (180, 180, 180)))
                landmarks.append((np.array([bx, 24.0, 3.0]), (180, 180, 180)))
                landmarks.append((np.array([-4.0, by, 3.0]), (180, 180, 180)))
                landmarks.append((np.array([4.0, by, 3.0]), (180, 180, 180)))
                
        # Camera intrinsic matrix K
        fx = self.width * 0.8
        fy = fx
        cx = self.width / 2.0
        cy = self.height / 2.0

        for i in range(num_frames):
            t = i / self.fps
            
            # Calculate Drone Position (X, Y, Z meters in ENU)
            if flight_type == "forward":
                cam_x = 0.0
                cam_y = i * 0.4
                cam_z = 15.0
                yaw = 0.0
                pitch = -30.0
            elif flight_type == "lateral":
                cam_x = (i - num_frames / 2.0) * 0.4
                cam_y = 10.0
                cam_z = 15.0
                yaw = 0.0
                pitch = -30.0
            elif flight_type == "orbit":
                radius = 18.0
                theta = (i / num_frames) * 2.0 * np.pi
                cam_x = radius * np.sin(theta)
                cam_y = 20.0 - radius * np.cos(theta)
                cam_z = 14.0
                yaw = float(np.degrees(theta))
                pitch = -25.0
            elif flight_type == "altitude":
                cam_x = 0.0
                cam_y = i * 0.2
                cam_z = 10.0 + (i * 0.3)  # Climbing altitude
                yaw = 0.0
                pitch = -35.0
            elif flight_type == "loop_closure":
                # Figures-8 or circle loop back
                theta = (i / num_frames) * 2.0 * np.pi
                cam_x = 12.0 * np.sin(theta)
                cam_y = 20.0 + 8.0 * np.cos(theta)
                cam_z = 15.0
                yaw = float(np.degrees(theta))
                pitch = -30.0
            else:
                cam_x = 0.0
                cam_y = i * 0.4
                cam_z = 15.0
                yaw = 0.0
                pitch = -30.0
                
            # GPS Noise injection
            gps_noise_x = np.random.normal(0, 1.8) if flight_type == "gps_noise" else 0.0
            gps_noise_y = np.random.normal(0, 1.8) if flight_type == "gps_noise" else 0.0
            gps_noise_z = np.random.normal(0, 1.8) if flight_type == "gps_noise" else 0.0
            
            # Render Synthetic Frame
            img = np.full((self.height, self.width, 3), (220, 200, 180), dtype=np.uint8)  # sky / background
            
            # Draw ground plane gradient
            img[self.height // 3:, :] = (60, 120, 60) if flight_type == "vegetation" else (130, 130, 130)
            
            # Camera orientation matrix
            yaw_rad = np.radians(yaw)
            pitch_rad = np.radians(pitch)
            
            Rz = np.array([
                [np.cos(yaw_rad), -np.sin(yaw_rad), 0],
                [np.sin(yaw_rad), np.cos(yaw_rad), 0],
                [0, 0, 1]
            ])
            Rx = np.array([
                [1, 0, 0],
                [0, np.cos(pitch_rad), -np.sin(pitch_rad)],
                [0, np.sin(pitch_rad), np.cos(pitch_rad)]
            ])
            R_wc = Rz @ Rx
            R_cw = R_wc.T
            cam_t = np.array([cam_x, cam_y, cam_z], dtype=np.float64)
            t_cw = -R_cw @ cam_t
            
            # Project 3D landmarks into frame
            for lm_pos, color in landmarks:
                pt_c = R_cw @ lm_pos + t_cw
                if pt_c[2] > 0.5:
                    u = int(round(fx * (pt_c[0] / pt_c[2]) + cx))
                    v = int(round(fy * (pt_c[1] / pt_c[2]) + cy))
                    if 0 <= u < self.width and 0 <= v < self.height:
                        radius = max(2, int(round(25.0 / pt_c[2])))
                        cv2.circle(img, (u, v), radius, color, -1)
                        
            # Apply motion blur if scenario calls for it
            if flight_type == "motion_blur" and i % 4 == 0:
                ksize = 15
                kernel = np.zeros((ksize, ksize))
                kernel[int((ksize-1)/2), :] = np.ones(ksize)
                kernel /= ksize
                img = cv2.filter2D(img, -1, kernel)
                
            out_writer.write(img)
            
            # Convert local ENU (cam_x, cam_y, cam_z) to GPS Lat/Lon (approximate conversion: 1 deg lat ~ 111,000m)
            lat = ref_lat + ((cam_y + gps_noise_y) / 111111.0)
            lon = ref_lon + ((cam_x + gps_noise_x) / (111111.0 * np.cos(np.radians(ref_lat))))
            alt = ref_alt + (cam_z + gps_noise_z)
            
            # Write SRT Subtitle entry
            s_start = int(t)
            ms_start = int((t - s_start) * 1000)
            t_next = (i + 1) / self.fps
            s_end = int(t_next)
            ms_end = int((t_next - s_end) * 1000)
            
            srt_block = f"""{i + 1}
00:00:{s_start:02d},{ms_start:03d} --> 00:00:{s_end:02d},{ms_end:03d}
[iso: 100] [shutter: 1/500] [fnum: 2.8] [latitude: {lat:.6f}] [longitude: {lon:.6f}] [rel_alt: {cam_z:.3f}] [abs_alt: {alt:.3f}] [yaw: {yaw:.2f}] [pitch: {pitch:.2f}] [roll: 0.00]
"""
            srt_lines.append(srt_block)
            
        out_writer.release()
        
        with open(srt_p, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
            
        return video_p, srt_p
