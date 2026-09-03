"""
Telemetry and GPS Ingestion, Normalization, WGS84 Geodetic to Local ENU Conversion,
and Video-to-Telemetry Timestamp Synchronization for SinglePass3D.
"""

from __future__ import annotations
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from singlepass3d.core.logging import get_logger
from singlepass3d.core.types import TelemetryPoint


# WGS84 Ellipsoid constants
WGS84_A = 6378137.0          # semi-major axis in meters
WGS84_B = 6356752.314245     # semi-minor axis in meters
WGS84_E2 = (WGS84_A**2 - WGS84_B**2) / (WGS84_A**2)  # first eccentricity squared


def geodetic_to_ecef(lat: float, lon: float, alt: float) -> np.ndarray:
    """
    Convert geodetic (lat, lon degrees, alt meters) to Earth-Centered Earth-Fixed (ECEF) XYZ in meters.
    """
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    sin_lat = np.sin(lat_rad)
    cos_lat = np.cos(lat_rad)
    sin_lon = np.sin(lon_rad)
    cos_lon = np.cos(lon_rad)
    
    N = WGS84_A / np.sqrt(1.0 - WGS84_E2 * sin_lat**2)
    x = (N + alt) * cos_lat * cos_lon
    y = (N + alt) * cos_lat * sin_lon
    z = (N * (1.0 - WGS84_E2) + alt) * sin_lat
    return np.array([x, y, z], dtype=np.float64)


def ecef_to_enu(ecef: np.ndarray, ref_lat: float, ref_lon: float, ref_alt: float) -> np.ndarray:
    """
    Convert ECEF coordinates to local East-North-Up (ENU) coordinates relative to a reference geodetic point.
    """
    ref_ecef = geodetic_to_ecef(ref_lat, ref_lon, ref_alt)
    d_ecef = ecef - ref_ecef
    
    lat_rad = np.radians(ref_lat)
    lon_rad = np.radians(ref_lon)
    sin_lat = np.sin(lat_rad)
    cos_lat = np.cos(lat_rad)
    sin_lon = np.sin(lon_rad)
    cos_lon = np.cos(lon_rad)
    
    # Rotation matrix from ECEF to ENU
    R = np.array([
        [-sin_lon, cos_lon, 0.0],
        [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
        [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat]
    ], dtype=np.float64)
    
    return R @ d_ecef


def enu_to_ecef(enu: np.ndarray, ref_lat: float, ref_lon: float, ref_alt: float) -> np.ndarray:
    """
    Convert local ENU coordinates back to ECEF XYZ.
    """
    ref_ecef = geodetic_to_ecef(ref_lat, ref_lon, ref_alt)
    lat_rad = np.radians(ref_lat)
    lon_rad = np.radians(ref_lon)
    sin_lat = np.sin(lat_rad)
    cos_lat = np.cos(lat_rad)
    sin_lon = np.sin(lon_rad)
    cos_lon = np.cos(lon_rad)
    
    R = np.array([
        [-sin_lon, cos_lon, 0.0],
        [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
        [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat]
    ], dtype=np.float64)
    
    return ref_ecef + (R.T @ enu)


def normalize_timestamps(raw: np.ndarray) -> np.ndarray:
    """
    Convert a whole column of log timestamps to seconds using one divisor.

    The unit has to be decided for the file as a whole, not per row: a log that
    starts at 7_009_129 and ends at 2_720_692_353 microseconds crosses any
    magnitude threshold you might test row by row, so the early records get
    scaled as milliseconds and the rest as microseconds. The sequence then no
    longer describes a flight at all. The sampling interval is the reliable
    signal instead - every plausible unit gives the same reading of it up to a
    power of a thousand, and only one of those readings puts consecutive samples
    within a few milliseconds to a few seconds of each other.
    """
    t = np.asarray(raw, dtype=np.float64)
    if t.size < 3:
        return t
    finite = t[np.isfinite(t)]
    if finite.size < 3:
        return t
    step = float(np.median(np.abs(np.diff(np.sort(finite)))))
    if not np.isfinite(step) or step <= 0.0:
        step = float(np.ptp(finite)) / max(1.0, finite.size - 1.0)
    best, best_cost = 1.0, float("inf")
    for div in (1.0, 1e3, 1e6, 1e9):
        dt = step / div
        if dt <= 0.0:
            continue
        # Sampling rates worth believing sit between 500 Hz and one sample per
        # 10 s; score by log-distance to that window's centre so the choice is
        # scale-free rather than a chain of magnitude tests.
        cost = abs(np.log(dt / 0.03))
        if dt < 1e-4 or dt > 30.0:
            cost += 12.0
        if cost < best_cost:
            best, best_cost = div, cost
    return t / best


class TelemetryParser:
    """
    Parses drone telemetry from SRT subtitles, CSV, or JSON logs, converts coordinates
    to local ENU metric frame, and synchronizes timestamps with video stream.
    """
    def __init__(self, telemetry_path: Optional[str | Path] = None):
        self.telemetry_path = Path(telemetry_path) if telemetry_path else None
        self.logger = get_logger()
        self.points: List[TelemetryPoint] = []
        self.datum_origin: Optional[Tuple[float, float, float]] = None  # (ref_lat, ref_lon, ref_alt)
        self.time_offset: float = 0.0
        # Populated when the log names the image each record belongs to.
        self.image_index: Dict[int, TelemetryPoint] = {}

    def parse(self) -> List[TelemetryPoint]:
        """
        Parses telemetry file into normalized TelemetryPoint list.
        """
        if self.telemetry_path is None or not self.telemetry_path.exists():
            self.logger.warning("No telemetry file provided or file does not exist. Using synthetic local metric datum.")
            return []
            
        suffix = self.telemetry_path.suffix.lower()
        if suffix == ".srt":
            raw_points = self._parse_srt(self.telemetry_path)
        elif suffix == ".csv":
            raw_points = self._parse_csv(self.telemetry_path)
        elif suffix in [".json", ".geojson"]:
            raw_points = self._parse_json(self.telemetry_path)
        else:
            raw_points = self._parse_generic_text(self.telemetry_path)
            
        if not raw_points:
            self.logger.warning(f"No valid telemetry points extracted from {self.telemetry_path}")
            return []
            
        # Set datum origin to first point
        self.datum_origin = (raw_points[0].latitude, raw_points[0].longitude, raw_points[0].altitude)
        ref_lat, ref_lon, ref_alt = self.datum_origin
        
        # Convert all to local ENU
        for pt in raw_points:
            ecef = geodetic_to_ecef(pt.latitude, pt.longitude, pt.altitude)
            enu = ecef_to_enu(ecef, ref_lat, ref_lon, ref_alt)
            pt.enu_x = float(enu[0])
            pt.enu_y = float(enu[1])
            pt.enu_z = float(enu[2])
            
        # Compute velocities by finite difference
        for i in range(len(raw_points)):
            if i > 0:
                dt = max(1e-4, raw_points[i].timestamp - raw_points[i - 1].timestamp)
                dx = raw_points[i].enu_x - raw_points[i - 1].enu_x
                dy = raw_points[i].enu_y - raw_points[i - 1].enu_y
                dz = raw_points[i].enu_z - raw_points[i - 1].enu_z
                raw_points[i].velocity = np.array([dx / dt, dy / dt, dz / dt], dtype=np.float64)
                if pt.heading == 0.0 and (dx**2 + dy**2) > 0.01:
                    raw_points[i].heading = float(np.degrees(np.arctan2(dx, dy)))
                    
        self.points = sorted(raw_points, key=lambda p: p.timestamp)
        self.image_index = {p.image_id: p for p in self.points if p.image_id > 0}
        self.logger.info(
            f"Parsed {len(self.points)} telemetry records. Datum origin: ({ref_lat:.6f}, {ref_lon:.6f}, {ref_alt:.2f}m)"
        )
        return self.points

    def _parse_srt(self, path: Path) -> List[TelemetryPoint]:
        """
        Parses DJI/drone SRT subtitle format.
        Example block:
        1
        00:00:00,000 --> 00:00:00,033
        [iso: 100] [shutter: 1/500] [fnum: 2.8] [latitude: 37.774900] [longitude: -122.419400] [rel_alt: 25.400] [abs_alt: 50.200]
        """
        points: List[TelemetryPoint] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        blocks = re.split(r"\n\s*\n", content.strip())
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if len(lines) < 2:
                continue
                
            # Time line: 00:00:01,234 --> 00:00:01,267
            time_match = re.search(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", lines[1] if len(lines) > 1 else lines[0])
            if not time_match:
                continue
                
            hours, mins, secs, ms = map(int, time_match.groups())
            t = hours * 3600.0 + mins * 60.0 + secs + ms / 1000.0
            
            text_block = " ".join(lines)
            
            # Extract coordinates
            lat_m = re.search(r"latitude\s*[:=]\s*([+-]?\d+\.?\d*)", text_block, re.IGNORECASE)
            lon_m = re.search(r"longitude\s*[:=]\s*([+-]?\d+\.?\d*)", text_block, re.IGNORECASE)
            abs_alt_m = re.search(r"abs_alt\s*[:=]\s*([+-]?\d+\.?\d*)", text_block, re.IGNORECASE)
            rel_alt_m = re.search(r"rel_alt\s*[:=]\s*([+-]?\d+\.?\d*)", text_block, re.IGNORECASE)
            alt_m = re.search(r"altitude\s*[:=]\s*([+-]?\d+\.?\d*)", text_block, re.IGNORECASE)
            yaw_m = re.search(r"yaw\s*[:=]\s*([+-]?\d+\.?\d*)", text_block, re.IGNORECASE)
            pitch_m = re.search(r"pitch\s*[:=]\s*([+-]?\d+\.?\d*)", text_block, re.IGNORECASE)
            roll_m = re.search(r"roll\s*[:=]\s*([+-]?\d+\.?\d*)", text_block, re.IGNORECASE)
            
            lat = float(lat_m.group(1)) if lat_m else 0.0
            lon = float(lon_m.group(1)) if lon_m else 0.0
            alt = float(abs_alt_m.group(1)) if abs_alt_m else (float(alt_m.group(1)) if alt_m else 0.0)
            rel_alt = float(rel_alt_m.group(1)) if rel_alt_m else 0.0
            yaw = float(yaw_m.group(1)) if yaw_m else 0.0
            pitch = float(pitch_m.group(1)) if pitch_m else 0.0
            roll = float(roll_m.group(1)) if roll_m else 0.0
            
            if abs(lat) > 1e-5 or abs(lon) > 1e-5:
                pt = TelemetryPoint(
                    timestamp=t,
                    latitude=lat,
                    longitude=lon,
                    altitude=alt if alt != 0.0 else rel_alt,
                    relative_altitude=rel_alt,
                    yaw=yaw,
                    pitch=pitch,
                    roll=roll,
                    uncertainty=1.0
                )
                points.append(pt)
                
        return points

    def _parse_csv(self, path: Path) -> List[TelemetryPoint]:
        rows: List[Dict[str, str]] = []
        raw_ts: List[float] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for row in csv.DictReader(f):
                lower_row = {str(k).lower().strip(): str(v).strip() for k, v in row.items() if k}
                try:
                    raw_ts.append(float(
                        lower_row.get("timestamp") or lower_row.get("time")
                        or lower_row.get("timpstemp") or lower_row.get("t") or 0.0
                    ))
                except Exception:
                    continue
                rows.append(lower_row)

        # The unit is a property of the file, so it is resolved once over every row.
        stamps = normalize_timestamps(np.asarray(raw_ts, dtype=np.float64))

        points: List[TelemetryPoint] = []
        for lower_row, t in zip(rows, stamps):
            try:
                lat = float(lower_row.get("latitude") or lower_row.get("lat") or 0.0)
                lon = float(lower_row.get("longitude") or lower_row.get("lon") or lower_row.get("lng") or 0.0)

                # If coordinates in 1e7 microdegrees (common in PX4 / Zurich logs)
                if abs(lat) > 90.0:
                    lat = lat / 1e7
                if abs(lon) > 180.0:
                    lon = lon / 1e7

                alt = float(lower_row.get("altitude") or lower_row.get("alt") or lower_row.get("abs_alt") or lower_row.get("height") or 0.0)
                rel_alt = float(lower_row.get("relative_altitude") or lower_row.get("rel_alt") or 0.0)
                yaw = float(lower_row.get("yaw") or lower_row.get("heading") or lower_row.get("omega_gt") or 0.0)
                pitch = float(lower_row.get("pitch") or lower_row.get("phi_gt") or 0.0)
                roll = float(lower_row.get("roll") or lower_row.get("kappa_gt") or 0.0)
                unc = float(lower_row.get("uncertainty") or lower_row.get("accuracy") or lower_row.get("eph_m") or 1.0)
                # Receivers routinely report a nonsense VDOP (denormalised floats
                # appear in PX4 logs); only believe it when it is physically sane.
                epv = float(lower_row.get("epv_m") or lower_row.get("vertical_accuracy") or 0.0)
                vunc = epv if 0.05 < epv < 500.0 else max(0.1, unc) * 1.6
                # An explicit image number is an exact frame correspondence; keep it.
                img = int(float(lower_row.get("imgid") or lower_row.get("image_id")
                                or lower_row.get("img_id") or lower_row.get("frame") or 0.0))

                if abs(lat) > 1e-5 or abs(lon) > 1e-5:
                    points.append(TelemetryPoint(
                        timestamp=float(t),
                        latitude=lat,
                        longitude=lon,
                        altitude=alt if alt != 0.0 else rel_alt,
                        relative_altitude=rel_alt,
                        yaw=yaw,
                        pitch=pitch,
                        roll=roll,
                        uncertainty=max(0.1, unc),
                        vertical_uncertainty=max(0.1, vunc),
                        image_id=max(0, img),
                    ))
            except Exception:
                continue
        return points

    def _parse_json(self, path: Path) -> List[TelemetryPoint]:
        points: List[TelemetryPoint] = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        items = data if isinstance(data, list) else data.get("records", data.get("telemetry", []))
        for item in items:
            pt = TelemetryPoint(
                timestamp=float(item.get("timestamp", 0.0)),
                latitude=float(item.get("latitude", item.get("lat", 0.0))),
                longitude=float(item.get("longitude", item.get("lon", 0.0))),
                altitude=float(item.get("altitude", item.get("alt", 0.0))),
                relative_altitude=float(item.get("relative_altitude", item.get("rel_alt", 0.0))),
                yaw=float(item.get("yaw", 0.0)),
                pitch=float(item.get("pitch", 0.0)),
                roll=float(item.get("roll", 0.0)),
                uncertainty=float(item.get("uncertainty", 1.0))
            )
            points.append(pt)
        return points

    def _parse_generic_text(self, path: Path) -> List[TelemetryPoint]:
        return self._parse_srt(path)

    def attach_barometric_altitude(self, path: str | Path, sigma_m: float = 0.35) -> bool:
        """
        Replaces the GNSS height channel with a barometric altitude series.

        A barometer measures *change* in height to a few centimetres, which is an
        order of magnitude better than a consumer GNSS fix and does not depend on
        satellite geometry. Absolute pressure altitude is biased, so the series is
        anchored to the GNSS datum and only its shape is used. This is what makes the
        vertical component trustworthy enough to set metric scale on flights whose
        horizontal extent is small compared with the GNSS error.
        """
        path = Path(path)
        if not self.points or not path.exists():
            return False
        ts: List[float] = []
        alt: List[float] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                low = {str(k).lower().strip(): str(v).strip() for k, v in row.items() if k}
                try:
                    raw_t = float(low.get("timestamp") or low.get("timpstemp") or low.get("time") or 0.0)
                    a = low.get("altitude") or low.get("alt") or low.get("height")
                    if a is None:
                        continue
                    a = float(a)
                except Exception:
                    continue
                if not (np.isfinite(raw_t) and np.isfinite(a)):
                    continue
                ts.append(raw_t)
                alt.append(a)
        if len(ts) < 8:
            return False
        # Same clock, same treatment: one divisor for the whole column.
        ts_arr = normalize_timestamps(np.asarray(ts, dtype=np.float64))
        order = np.argsort(ts_arr)
        ts_a = ts_arr[order]
        alt_a = np.asarray(alt, dtype=np.float64)[order]
        # A barometer is noisy sample to sample but very stable over seconds; smoothing
        # over roughly a second removes the pressure ripple without touching the climb.
        span = max(1e-6, float(ts_a[-1] - ts_a[0]))
        win = int(np.clip(round(len(ts_a) / max(1.0, span)), 1, 199)) | 1
        if win > 1:
            k = np.ones(win) / win
            alt_a = np.convolve(np.pad(alt_a, win // 2, mode="edge"), k, mode="valid")[:len(ts_a)]
        pt_t = np.asarray([p.timestamp for p in self.points], dtype=np.float64)
        overlap = float(min(ts_a[-1], pt_t.max()) - max(ts_a[0], pt_t.min()))
        if overlap < 0.5 * (pt_t.max() - pt_t.min()):
            self.logger.warning("Barometric log does not overlap the telemetry window; keeping GNSS height.")
            return False
        sampled = np.interp(pt_t, ts_a, alt_a)
        gps_z = np.asarray([p.enu_z for p in self.points], dtype=np.float64)
        # Anchor to the GNSS height so georeferencing keeps its absolute datum, and
        # take only the barometer's shape from there.
        offset = float(np.median(gps_z - sampled))
        for pt, z in zip(self.points, sampled):
            pt.enu_z = float(z + offset)
            pt.vertical_uncertainty = float(sigma_m)
        self.logger.info(
            f"Barometric altitude fused over {len(self.points)} records: "
            f"climb {float(sampled.max() - sampled.min()):.2f} m against "
            f"{float(gps_z.max() - gps_z.min()):.2f} m from GNSS "
            f"(vertical sigma {sigma_m:.2f} m vs horizontal "
            f"{float(np.median([p.uncertainty for p in self.points])):.2f} m)."
        )
        return True

    def align_to_image_sequence(self, indexer: Any) -> bool:
        """
        Bind frames to telemetry records by image number instead of by clock.

        When the log names the image each record belongs to there is nothing left to
        estimate: record `imgid = k` *is* the measurement for image k. Cross-correlating
        speed profiles to recover an offset can only be worse, and on a near-hover clip
        it is far worse - the visual speed signal carries almost no structure to lock
        onto, so the search settles on an arbitrary lag and the reconstruction ends up
        anchored to a slice of the flight that the images never saw.

        Frame timestamps are rewritten to the matched record's own clock, so every
        later telemetry query resolves exactly without a residual offset.
        """
        index = getattr(self, "image_index", None)
        frames = getattr(indexer, "frame_index", None)
        if not index or not frames:
            return False
        matched = 0
        for meta in frames.values():
            src = getattr(meta, "fullres_path", None)
            if not src:
                continue
            stem = Path(src).stem
            digits = re.findall(r"\d+", stem)
            if not digits:
                continue
            pt = index.get(int(digits[-1]))
            if pt is None:
                continue
            meta.timestamp = float(pt.timestamp)
            matched += 1
        if matched < max(3, int(0.6 * len(frames))):
            if matched:
                self.logger.warning(
                    f"Flight log names images but only {matched} of {len(frames)} frames matched; "
                    "falling back to timestamp correlation."
                )
            return False
        self.time_offset = 0.0
        stamps = sorted(float(m.timestamp) for m in frames.values())
        self.logger.info(
            f"Frames bound to flight log by image number: {matched}/{len(frames)} matched, "
            f"covering log time {stamps[0]:.2f}-{stamps[-1]:.2f} s "
            f"({stamps[-1] - stamps[0]:.2f} s of flight)."
        )
        return True

    def estimate_video_time_offset(self, video_timestamps: List[float], visual_speed_estimates: Optional[List[float]] = None) -> float:
        """
        Estimates time offset between video timestamps and GPS telemetry timestamps.
        """
        if not self.points or not video_timestamps:
            self.time_offset = 0.0
            return 0.0
            
        # Initial alignment: align start of video with start of telemetry
        t_telemetry_start = self.points[0].timestamp
        t_video_start = video_timestamps[0]
        self.time_offset = t_telemetry_start - t_video_start
        self.logger.info(f"Estimated video-to-telemetry time offset: {self.time_offset:.3f}s")
        return self.time_offset

    def get_telemetry_at(self, video_timestamp: float) -> Optional[TelemetryPoint]:
        """
        Query interpolated telemetry at a given video timestamp (adjusted by time_offset).
        """
        if not self.points:
            return None
            
        query_t = video_timestamp + self.time_offset
        ts = [p.timestamp for p in self.points]
        
        if query_t <= ts[0]:
            return self.points[0]
        if query_t >= ts[-1]:
            return self.points[-1]
            
        idx = np.searchsorted(ts, query_t)
        p0 = self.points[idx - 1]
        p1 = self.points[idx]
        dt = max(1e-6, p1.timestamp - p0.timestamp)
        alpha = (query_t - p0.timestamp) / dt
        
        interp_pt = TelemetryPoint(
            timestamp=query_t,
            latitude=(1 - alpha) * p0.latitude + alpha * p1.latitude,
            longitude=(1 - alpha) * p0.longitude + alpha * p1.longitude,
            altitude=(1 - alpha) * p0.altitude + alpha * p1.altitude,
            relative_altitude=(1 - alpha) * p0.relative_altitude + alpha * p1.relative_altitude,
            yaw=(1 - alpha) * p0.yaw + alpha * p1.yaw,
            pitch=(1 - alpha) * p0.pitch + alpha * p1.pitch,
            roll=(1 - alpha) * p0.roll + alpha * p1.roll,
            velocity=(1 - alpha) * p0.velocity + alpha * p1.velocity,
            heading=(1 - alpha) * p0.heading + alpha * p1.heading,
            uncertainty=max(p0.uncertainty, p1.uncertainty),
            vertical_uncertainty=max(p0.vertical_uncertainty, p1.vertical_uncertainty),
            enu_x=(1 - alpha) * p0.enu_x + alpha * p1.enu_x,
            enu_y=(1 - alpha) * p0.enu_y + alpha * p1.enu_y,
            enu_z=(1 - alpha) * p0.enu_z + alpha * p1.enu_z,
        )
        return interp_pt
