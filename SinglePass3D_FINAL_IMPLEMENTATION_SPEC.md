# SinglePass3D — Final Implementation Specification

## Objective

Build a high-quality single-pass drone-video-to-3D reconstruction system.

Input:
- one moving RGB drone video
- GPS/flight telemetry
- optional IMU/camera metadata

Output:
- accurate GPS-anchored 3D geometry
- high-resolution textures
- GLB/PLY/OBJ
- camera trajectory
- confidence/provenance data
- reconstruction-quality report

The system must treat the video as a continuous multi-view measurement sequence.

Do NOT build a pipeline that simply samples a few frames, predicts monocular depth, runs Poisson reconstruction, and calls the result a 3D model.

The central state of the system is a continuously refined 3D world representation.

Modern research directly motivates this design: VGGT predicts camera parameters, point maps, depth and tracks from multiple views; CUT3R maintains a persistent state and accumulates metric pointmaps from image streams; SLAM3R reconstructs overlapping video windows and progressively registers their dense pointmaps. These are the right foundations for this problem, but GPS and classical geometric verification must be added because the target is metric drone reconstruction rather than merely visually plausible reconstruction. citeturn0search2turn0search0turn0search1

---

# 1. CORE ARCHITECTURE

The pipeline has exactly six conceptual layers:

1. SENSOR LAYER
   - video
   - timestamps
   - GPS
   - optional IMU
   - camera metadata

2. CONTINUOUS GEOMETRY LAYER
   - visual tracking
   - VGGT/CUT3R/MASt3R-family inference
   - local pointmaps
   - camera estimates
   - 3D tracks

3. METRIC WORLD LAYER
   - GPS alignment
   - persistent world map
   - confidence-weighted fusion
   - global optimization
   - loop closure

4. EVIDENCE LAYER
   - multi-view reprojection
   - visibility
   - uncertainty
   - semantic/dynamic filtering
   - observed vs inferred classification

5. COMPLETION LAYER
   - structural completion
   - optional generative completion
   - completion validation

6. OUTPUT LAYER
   - high-resolution texture
   - mesh
   - GLB
   - QA/reporting

Do not merge these layers into one monolithic reconstruction function.

---

# 2. THE MOST IMPORTANT RULE

The mesh is NOT the reconstruction state.

The persistent world state is.

Represent the world as spatially indexed surface elements:

    WorldElement
      position
      normal
      covariance
      color observations
      supporting frames
      supporting rays
      observation count
      reprojection error
      model confidence
      GPS/trajectory confidence
      semantic class
      dynamic probability
      visibility
      provenance
      state

Possible provenance:

    OBSERVED
    MULTI_VIEW_SUPPORTED
    STRUCTURAL_INFERRED
    GENERATIVE_INFERRED

Possible visibility state:

    VISIBLE
    OCCLUDED
    UNKNOWN

Every later stage must preserve this information.

---

# 3. VIDEO MUST BE USED AS A CONTINUOUS SENSOR

Never reduce a good drone video to 20–30 arbitrary frames.

Decode the full sequence.

Use three frame populations:

### Tracking frames
High temporal frequency.

Purpose:
- optical flow
- feature tracking
- motion estimation
- dynamic detection

### Reconstruction frames
Adaptive selection.

Purpose:
- learned multi-view reconstruction
- dense geometry
- global alignment

### Refinement frames
Original-resolution frames selected later.

Purpose:
- facade detail
- roof detail
- texture
- local geometry refinement

Frame selection must depend on:

- translation
- angular motion
- baseline
- parallax
- overlap
- sharpness
- feature density
- image novelty
- scene coverage

Fixed FPS sampling is only a fallback.

---

# 4. INGESTION

Preserve the original video.

Create an indexed frame store.

For each frame store:

    frame_id
    timestamp
    original_index
    resolution
    sharpness
    blur
    exposure
    saturation
    feature_count
    optical_flow
    dynamic_probability

Do not permanently resize the source.

Use low-resolution frames for cheap analysis and original-resolution frames for refinement.

---

# 5. GPS / TELEMETRY

Parse:

- embedded metadata
- SRT
- CSV
- JSON
- EXIF
- supported drone flight logs

Normalize to:

    timestamp
    latitude
    longitude
    altitude
    yaw
    pitch
    roll
    velocity
    heading
    uncertainty

Convert GPS to local ENU coordinates.

Estimate video-to-GPS timestamp offset.

Do not assume timestamps match exactly.

GPS is a noisy measurement.

Use it as a global constraint, not an absolute command.

---

# 6. CAMERA MODEL

Support:

- known intrinsics
- estimated intrinsics
- distortion
- fisheye
- rolling shutter where necessary
- camera/GPS lever arm

Estimate or obtain:

    fx
    fy
    cx
    cy
    distortion
    camera-to-GPS transform

Do not hardcode focal length.

Keep calibration uncertainty.

---

# 7. VISUAL TRAJECTORY

Estimate the continuous camera trajectory using:

    visual tracking
    learned correspondences
    classical feature matching
    GPS
    optional IMU
    loop closures

Use SIFT/RootSIFT and optical flow as robust fallbacks.

Use learned correspondence models where available.

Maintain long tracks.

Reject tracks with:

- inconsistent motion
- high reprojection error
- blur
- short duration
- dynamic behavior

The trajectory must be a continuous object.

Do not estimate each reconstruction window independently and then concatenate poses.

---

# 8. GPS-CONSTRAINED TRAJECTORY OPTIMIZATION

Create a factor graph / nonlinear optimization problem.

Variables:

    camera poses
    selected landmarks
    camera intrinsics if uncertain
    camera-GPS transform if uncertain

Factors:

    visual reprojection
    GPS position
    optional IMU
    temporal smoothness
    loop closure
    learned pose prior

Use robust losses.

GPS should determine:

- global metric scale
- global translation
- global orientation when heading/trajectory provides sufficient constraint

Visual geometry determines local structure.

Do not force every GPS measurement exactly.

---

# 9. LEARNED 3D RECONSTRUCTION

Implement adapters for:

1. VGGT
2. CUT3R
3. MASt3R/DUSt3R family
4. SLAM3R where useful

The first production implementation should use the strongest compatible model available rather than implementing every model simultaneously.

VGGT is particularly useful because it directly predicts cameras, depth, point maps and 3D tracks from multiple views. citeturn0search2turn0search8

CUT3R is particularly useful for continuous processing because its persistent state accumulates pointmaps in a common coordinate system. citeturn0search0turn0search6

SLAM3R is particularly relevant to the exact video setting because it uses overlapping clips and progressively registers local dense pointmaps into a global reconstruction. citeturn0search1turn0search45

Do not blindly trust their geometry.

Their output is evidence.

---

# 10. OVERLAPPING WINDOWS

For long videos, process overlapping windows.

A window contains enough viewpoint change for meaningful geometry but remains within GPU memory.

Adjacent windows MUST overlap.

Each window produces:

    pointmaps
    confidence
    tracks
    camera estimates
    local coordinate system

Never:

    window A -> mesh
    window B -> mesh
    concatenate meshes

Instead:

    window A -> pointmap
    window B -> pointmap
    overlap correspondence
    registration
    persistent world fusion

---

# 11. PERSISTENT WORLD UPDATE

As every reconstruction window arrives:

1. find overlap with current world
2. register local geometry
3. compare with existing geometry
4. compute confidence
5. fuse compatible observations
6. retain conflicting hypotheses temporarily
7. reject persistent contradictions
8. update surface uncertainty

Never overwrite high-confidence geometry with one new prediction.

Use multiple observations to increase confidence.

---

# 12. CLASSICAL GEOMETRY AS INDEPENDENT VERIFICATION

Run a classical SfM path on high-quality reconstruction frames.

Use COLMAP/PyCOLMAP where available.

Recover:

    feature tracks
    camera poses
    sparse landmarks
    triangulation
    reprojection errors

Use this as an independent geometric signal.

Where learned geometry and classical triangulation agree:

    confidence ↑

Where they disagree:

    do not immediately choose either
    run additional matching/reprojection tests

This independence is intentional.

---

# 13. MULTI-VIEW REPROJECTION IS THE PRIMARY QUALITY TEST

For every important surface element:

1. identify source observations
2. identify other frames that should see it
3. project its 3D position into those frames
4. compare against image evidence
5. calculate reprojection error
6. calculate visibility consistency
7. calculate depth-order consistency
8. calculate normal consistency

Geometry that repeatedly fails reprojection must lose confidence.

This is more important than whether the mesh visually looks smooth.

---

# 14. WORLD CONFIDENCE

Calculate confidence from:

    number of supporting views
    triangulation angle
    image sharpness
    learned confidence
    correspondence confidence
    reprojection error
    trajectory confidence
    GPS confidence
    local surface consistency
    semantic class
    dynamic probability
    occlusion

Example hierarchy:

    HIGH
      multiple views
      strong baseline
      low reprojection error
      independent agreement

    MEDIUM
      limited views
      reasonable learned prediction
      moderate geometric support

    LOW
      weak observation
      poor baseline
      inconsistent evidence

    UNKNOWN
      no actual evidence

Confidence must control fusion and meshing.

---

# 15. DYNAMIC OBJECT REMOVAL

Detect:

    people
    cars
    moving equipment
    animals
    temporary objects

Use:

    semantic segmentation
    temporal consistency
    multi-view motion

Do not fuse moving objects into the static world.

---

# 16. SEMANTIC-AWARE GEOMETRY

Minimum classes:

    ground
    road
    building
    facade
    roof
    vegetation
    water
    vehicle
    person
    unknown

Use semantics to change geometry processing.

### Buildings

Preserve:

- planar walls
- sharp corners
- roof planes
- vertical structure

### Ground

Preserve:

- terrain slope
- roads
- elevation changes

Do not flatten the whole scene.

### Vegetation

Lower confidence.

Do not let foliage become false hard-surface geometry.

---

# 17. ARCHITECTURAL REFINEMENT

For building/facade/roof regions:

1. estimate normals
2. detect dominant planes
3. detect structural edges
4. detect corners
5. fit planes robustly
6. preserve observed deviations
7. continue planes only through small unsupported gaps
8. use gravity for vertical alignment when justified
9. use parallelism only when evidence supports it

Do NOT convert the entire building into an idealized CAD block.

Real measured geometry must win.

---

# 18. GLOBAL REFINEMENT

After the complete flight has been processed:

1. optimize trajectory
2. optimize local reconstruction transforms
3. update GPS alignment
4. update landmarks
5. re-evaluate world observations
6. re-fuse geometry
7. re-run reprojection validation

Perform at least one full offline refinement pass.

For long flights, loop closure must be included.

---

# 19. LOOP CLOSURE

Detect revisits using:

- visual descriptors
- learned matching
- GPS proximity
- geometric verification

A valid loop closure should:

    add a constraint
    optimize trajectory
    correct drift
    update world geometry

Do not simply transform the final mesh after the fact.

---

# 20. HIGH-RESOLUTION REFINEMENT

Once global geometry is stable:

Find regions where:

    confidence is high
    detail matters
    original imagery contains additional information

Reprocess those regions at original resolution.

Use:

- facade crops
- roof crops
- structural edges
- high-quality texture frames

Only accept the refined geometry if it improves cross-view consistency.

---

# 21. UNKNOWN SURFACE MODEL

Do not pretend every surface is observed.

Explicitly maintain:

    OBSERVED
    OCCLUDED
    UNKNOWN

Example:

If the drone only sees the front of a building:

    front = observed
    side = possibly inferred
    back = unknown

This is critical.

---

# 22. STRUCTURAL COMPLETION

Before generative AI:

Use only geometry-supported completion:

    plane continuation
    boundary continuation
    small hole interpolation
    repeated architectural pattern
    strong symmetry

Do not use this to invent a completely unseen building side.

---

# 23. GENERATIVE COMPLETION

Generative AI is NOT allowed to repair the measured reconstruction.

It may operate only on regions classified UNKNOWN.

For each candidate region:

1. define boundary geometry
2. define semantic class
3. define neighboring planes
4. generate multiple candidate completions
5. convert candidate to explicit geometry
6. connect to observed boundaries
7. render candidate into source views
8. test boundary/silhouette/depth consistency
9. reject contradictory candidates
10. retain only the best defensible candidate

Label the result:

    GENERATIVE_INFERRED

Never label it observed.

If there is insufficient evidence:

    leave UNKNOWN

A missing surface is preferable to false precision.

---

# 24. TEXTURE RECONSTRUCTION

Texture is a separate optimization.

For every surface:

1. find all visible frames
2. calculate viewing angle
3. calculate sharpness
4. calculate exposure
5. calculate occlusion
6. select best pixels
7. blend across views
8. remove seams
9. preserve source detail

Use original-resolution images.

Do not use a blurry frame when a sharp frame exists.

---

# 25. MESH GENERATION

Only after world geometry is stable.

Use:

    TSDF / volumetric fusion
    screened Poisson where appropriate
    surface reconstruction appropriate to density

Use different settings for:

    terrain
    buildings
    thin structures
    vegetation

Do not force one watertight mesh.

Do not fill huge unknown regions.

Preserve high-confidence edges.

---

# 26. APPEARANCE REPRESENTATION

Optionally generate 3D Gaussian Splatting for visual inspection and novel-view rendering.

Do not treat splat appearance as geometric truth.

The explicit world geometry remains authoritative.

---

# 27. OUTPUT

Produce:

    model.glb
    model.ply
    model.obj
    trajectory.json
    cameras.json
    world.json
    uncertainty.json
    overlay.json
    quality.json
    report.json
    diagnostics.json

Overlay must contain:

    vertex/face/region provenance
    confidence
    semantic class
    supporting frames

---

# 28. QUALITY GATES

Do not declare success because a mesh exists.

Require:

### Trajectory

- no catastrophic drift
- GPS consistency
- stable orientation

### Geometry

- sufficient multi-view support
- acceptable reprojection error
- no large floating regions
- no catastrophic scale distortion

### Completeness

Report:

    observed %
    inferred %
    generative %
    unknown %

### Mesh

Check:

    degenerate triangles
    disconnected artifacts
    non-manifold geometry
    excessive smoothing

### Texture

Check:

    coverage
    sharpness
    seams

---

# 29. FAILURE BEHAVIOR

Never silently fabricate.

If geometry is weak:

    reduce confidence

If a region is unsupported:

    UNKNOWN

If GPS is inconsistent:

    report telemetry problem

If visual tracking fails:

    use learned geometry / available telemetry

If learned geometry disagrees with observations:

    reject or downweight it

If a generated completion cannot be validated:

    reject it

---

# 30. PERFORMANCE STRATEGY

Do NOT process every frame with every expensive model.

Use:

    all frames
        ↓
    cheap tracking/quality
        ↓
    adaptive reconstruction frames
        ↓
    expensive multi-view inference
        ↓
    targeted original-resolution refinement

Cache every expensive result.

The pipeline must resume after interruption.

---

# 31. IMPLEMENTATION ORDER

Implement exactly in this order:

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

Do not implement generative completion before validated reconstruction works.

---

# 32. REQUIRED TESTS

Create tests for:

- forward flight
- lateral flight
- orbit
- altitude change
- long flight
- GPS noise
- motion blur
- low-texture wall
- repeated buildings
- vegetation
- vehicles
- occlusion
- loop closure
- unseen surfaces

Also create one real-video regression test.

Record metrics before/after every major change.

---

# 33. REQUIRED CLI

Implement:

    python scripts/run_reconstruction.py \
      --video input.mp4 \
      --telemetry flight.srt \
      --output outputs/job_001 \
      --quality ultra

Also:

    python scripts/inspect_job.py outputs/job_001

and:

    python scripts/benchmark.py outputs/job_001

---

# 34. FINAL IMPLEMENTATION RULE

Do not simplify this architecture into:

    frames -> depth -> point cloud -> Poisson -> GLB

That architecture is the failure mode this project is specifically designed to eliminate.

Build:

    continuous video
        -> continuous camera/geometry estimation
        -> GPS metric anchoring
        -> persistent world
        -> independent geometric verification
        -> global optimization
        -> multi-view validation
        -> targeted high-resolution refinement
        -> constrained completion
        -> texture
        -> mesh

The final model must be the result of accumulated evidence from the entire flight.

The system should always prefer:

    measured geometry > multi-view inference > structural inference > generative inference

Never reverse that order.

Do not claim accuracy that the video cannot support.
