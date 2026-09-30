from pathlib import Path
import csv
import json
import shutil

import cv2
import numpy as np


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


# ============================================================
# INTERNAL HELPER
# ============================================================

def _clear_folder(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    for path in folder.iterdir():
        if path.is_file():
            path.unlink()


# ============================================================
# VIDEO INSPECTION
# ============================================================

def inspect_video(video_path):
    video_path = Path(video_path)

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS))
    source_frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if fps > 0:
        duration_seconds = source_frame_count / fps
    else:
        duration_seconds = 0.0

    fourcc_value = int(cap.get(cv2.CAP_PROP_FOURCC))

    codec = "".join(
        chr((fourcc_value >> (8 * i)) & 0xFF)
        for i in range(4)
    ).rstrip("\x00")

    cap.release()

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": duration_seconds,
        "source_frame_count": source_frame_count,
        "codec": codec if codec else None
    }


# ============================================================
# FRAME EXTRACTION
# ============================================================

def extract_frames(
    video_path,
    output_folder,
    sample_fps=2.0
):
    video_path = Path(video_path)
    output_folder = Path(output_folder)

    _clear_folder(output_folder)

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS))

    if fps <= 0:
        cap.release()
        raise RuntimeError("Invalid video FPS.")

    if sample_fps <= 0:
        cap.release()
        raise ValueError("sample_fps must be greater than zero.")

    # PRESERVED ORIGINAL ALGORITHM
    frame_interval = max(
        1,
        round(fps / sample_fps)
    )

    records = []

    source_frame_index = 0
    saved_frames = 0

    while True:

        success, frame = cap.read()

        if not success:
            break

        if source_frame_index % frame_interval == 0:

            filename = (
                f"frame_{saved_frames:05d}.jpg"
            )

            output_path = output_folder / filename

            success_write = cv2.imwrite(
                str(output_path),
                frame
            )

            if not success_write:
                cap.release()
                raise RuntimeError(
                    f"Could not save frame: {output_path}"
                )

            timestamp_seconds = (
                source_frame_index / fps
            )

            records.append({
                "filename": filename,
                "source_frame_index":
                    source_frame_index,
                "timestamp_seconds":
                    timestamp_seconds
            })

            saved_frames += 1

        source_frame_index += 1

    cap.release()

    return records


# ============================================================
# BLUR DETECTION
# ============================================================

def detect_blur(
    input_folder,
    good_folder,
    blurry_folder,
    blur_threshold=100.0
):
    input_folder = Path(input_folder)
    good_folder = Path(good_folder)
    blurry_folder = Path(blurry_folder)

    _clear_folder(good_folder)
    _clear_folder(blurry_folder)

    results = {}

    frame_files = sorted([
        path
        for path in input_folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    ])

    for path in frame_files:

        image = cv2.imread(str(path))

        if image is None:
            continue

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        # PRESERVED ORIGINAL ALGORITHM
        laplacian = cv2.Laplacian(
            gray,
            cv2.CV_64F
        )

        blur_score = float(
            laplacian.var()
        )

        # Easy-to-preserve additional metadata.
        # This does NOT affect any decision.
        brightness = float(
            np.mean(gray)
        )

        accepted = (
            blur_score >= blur_threshold
        )

        if accepted:

            destination = (
                good_folder / path.name
            )

            state = "accepted"

        else:

            destination = (
                blurry_folder / path.name
            )

            state = "rejected"

        shutil.copy2(
            path,
            destination
        )

        results[path.name] = {
            "blur_score": blur_score,
            "brightness": brightness,
            "accepted": accepted,
            "state": state
        }

    return results


# ============================================================
# BLUR ANALYSIS
# ============================================================

def analyze_blur(
    input_folder,
    output_folder,
    limit=10
):
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    _clear_folder(output_folder)

    scores = []

    frame_files = sorted([
        path
        for path in input_folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    ])

    for path in frame_files:

        image = cv2.imread(str(path))

        if image is None:
            continue

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        blur_score = float(
            cv2.Laplacian(
                gray,
                cv2.CV_64F
            ).var()
        )

        scores.append(
            (path.name, blur_score)
        )

    # PRESERVED ORIGINAL ALGORITHM
    scores.sort(
        key=lambda item: item[1]
    )

    for filename, score in scores[:limit]:

        shutil.copy2(
            input_folder / filename,
            output_folder / filename
        )

    return scores


# ============================================================
# STABILIZATION
# ============================================================

def stabilize_frames(
    input_folder,
    output_folder
):
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    _clear_folder(output_folder)

    frame_files = sorted([
        path
        for path in input_folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    ])

    if len(frame_files) < 2:
        raise RuntimeError(
            "Not enough frames for stabilization."
        )

    first_frame = cv2.imread(
        str(frame_files[0])
    )

    if first_frame is None:
        raise RuntimeError(
            "Could not read first frame."
        )

    previous_gray = cv2.cvtColor(
        first_frame,
        cv2.COLOR_BGR2GRAY
    )

    cv2.imwrite(
        str(
            output_folder /
            frame_files[0].name
        ),
        first_frame
    )

    for current_path in frame_files[1:]:

        current_frame = cv2.imread(
            str(current_path)
        )

        if current_frame is None:
            continue

        current_gray = cv2.cvtColor(
            current_frame,
            cv2.COLOR_BGR2GRAY
        )

        # PRESERVED ORIGINAL ALGORITHM
        previous_points = (
            cv2.goodFeaturesToTrack(
                previous_gray,
                maxCorners=300,
                qualityLevel=0.01,
                minDistance=30,
                blockSize=3
            )
        )

        if previous_points is None:

            cv2.imwrite(
                str(
                    output_folder /
                    current_path.name
                ),
                current_frame
            )

            previous_gray = current_gray
            continue

        current_points, status, error = (
            cv2.calcOpticalFlowPyrLK(
                previous_gray,
                current_gray,
                previous_points,
                None
            )
        )

        if current_points is None:

            cv2.imwrite(
                str(
                    output_folder /
                    current_path.name
                ),
                current_frame
            )

            previous_gray = current_gray
            continue

        good_previous = (
            previous_points[
                status.flatten() == 1
            ]
        )

        good_current = (
            current_points[
                status.flatten() == 1
            ]
        )

        if len(good_previous) >= 4:

            transformation, inliers = (
                cv2.estimateAffinePartial2D(
                    good_current,
                    good_previous,
                    method=cv2.RANSAC
                )
            )

        else:

            transformation = None

        if transformation is not None:

            height, width = (
                current_frame.shape[:2]
            )

            stabilized_frame = (
                cv2.warpAffine(
                    current_frame,
                    transformation,
                    (width, height),
                    flags=cv2.INTER_LINEAR,
                    borderMode=
                        cv2.BORDER_REFLECT
                )
            )

        else:

            stabilized_frame = (
                current_frame
            )

        cv2.imwrite(
            str(
                output_folder /
                current_path.name
            ),
            stabilized_frame
        )

        previous_gray = current_gray

    return len(frame_files)


# ============================================================
# KEYFRAME SELECTION
# ============================================================

def select_keyframes(
    input_folder,
    output_folder,
    difference_threshold=12.0
):
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    _clear_folder(output_folder)

    frame_files = sorted([
        path
        for path in input_folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower()
            in IMAGE_EXTENSIONS
        )
    ])

    if len(frame_files) == 0:
        raise RuntimeError(
            "No frames found."
        )

    first_frame = cv2.imread(
        str(frame_files[0])
    )

    if first_frame is None:
        raise RuntimeError(
            "Could not read first frame."
        )

    previous_gray = cv2.cvtColor(
        first_frame,
        cv2.COLOR_BGR2GRAY
    )

    # PRESERVED ORIGINAL SIZE
    previous_gray = cv2.resize(
        previous_gray,
        (320, 180)
    )

    # First frame always selected.
    shutil.copy2(
        frame_files[0],
        output_folder /
        frame_files[0].name
    )

    selections = [{
        "filename":
            frame_files[0].name,
        "selected": True,
        "difference_score": None
    }]

    for current_path in frame_files[1:]:

        current_frame = cv2.imread(
            str(current_path)
        )

        if current_frame is None:
            continue

        current_gray = cv2.cvtColor(
            current_frame,
            cv2.COLOR_BGR2GRAY
        )

        current_gray_small = (
            cv2.resize(
                current_gray,
                (320, 180)
            )
        )

        # PRESERVED ORIGINAL ALGORITHM
        difference = cv2.absdiff(
            previous_gray,
            current_gray_small
        )

        difference_score = float(
            np.mean(difference)
        )

        selected = (
            difference_score
            >= difference_threshold
        )

        if selected:

            shutil.copy2(
                current_path,
                output_folder /
                current_path.name
            )

            # IMPORTANT:
            # Future frames are compared against
            # most recently selected keyframe.
            previous_gray = (
                current_gray_small
            )

        selections.append({
            "filename":
                current_path.name,
            "selected":
                selected,
            "difference_score":
                difference_score
        })

    return selections


# ============================================================
# CSV HELPER
# ============================================================

def _write_csv(
    path,
    rows,
    fieldnames
):
    path = Path(path)

    with path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# HIGH-LEVEL PIPELINE
# ============================================================

def run_preprocessing(
    video_path,
    output_root,
    sample_fps=2.0,
    blur_threshold=100.0,
    difference_threshold=12.0,
    enable_stabilization=False
):
    video_path = Path(video_path)
    output_root = Path(output_root)

    output_root.mkdir(
        parents=True,
        exist_ok=True
    )

    extracted_folder = (
        output_root /
        "extracted_frames"
    )

    good_folder = (
        output_root /
        "good_frames"
    )

    blurry_folder = (
        output_root /
        "blurry_frames"
    )

    lowest_blur_folder = (
        output_root /
        "lowest_blur_scores"
    )

    keyframes_folder = (
        output_root /
        "keyframes"
    )

    stabilized_folder = (
        output_root /
        "stabilized_frames"
    )

    # --------------------------------------------------------
    # 1. VIDEO METADATA
    # --------------------------------------------------------

    video_metadata = (
        inspect_video(video_path)
    )

    video_metadata_path = (
        output_root /
        "video_metadata.json"
    )

    with video_metadata_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            video_metadata,
            file,
            indent=2
        )

    # --------------------------------------------------------
    # 2. FRAME EXTRACTION
    # --------------------------------------------------------

    frame_records = extract_frames(
        video_path,
        extracted_folder,
        sample_fps
    )

    # --------------------------------------------------------
    # 3. BLUR ANALYSIS
    # --------------------------------------------------------

    blur_results = detect_blur(
        extracted_folder,
        good_folder,
        blurry_folder,
        blur_threshold
    )

    analyze_blur(
        extracted_folder,
        lowest_blur_folder
    )

    # --------------------------------------------------------
    # 4. KEYFRAME SELECTION
    #
    # IMPORTANT:
    # ORIGINAL extracted frames are used.
    # Stabilized frames are NEVER used here.
    # --------------------------------------------------------

    keyframe_results = (
        select_keyframes(
            extracted_folder,
            keyframes_folder,
            difference_threshold
        )
    )

    # --------------------------------------------------------
    # 5. OPTIONAL STABILIZATION
    # --------------------------------------------------------

    if enable_stabilization:

        stabilize_frames(
            extracted_folder,
            stabilized_folder
        )

    elif stabilized_folder.exists():

        # Prevent old stabilization results
        # from being confused with this run.
        shutil.rmtree(
            stabilized_folder
        )

    # --------------------------------------------------------
    # 6. BUILD FRAME METADATA
    # --------------------------------------------------------

    keyframe_lookup = {
        item["filename"]: item
        for item in keyframe_results
    }

    frame_metadata_rows = []
    keyframe_manifest_rows = []

    keyframe_id = 0

    for record in frame_records:

        filename = record["filename"]

        blur_data = (
            blur_results.get(
                filename,
                {}
            )
        )

        keyframe_data = (
            keyframe_lookup.get(
                filename,
                {}
            )
        )

        selected = bool(
            keyframe_data.get(
                "selected",
                False
            )
        )

        difference_score = (
            keyframe_data.get(
                "difference_score"
            )
        )

        frame_row = {
            "filename":
                filename,

            "source_frame_index":
                record[
                    "source_frame_index"
                ],

            "timestamp_seconds":
                record[
                    "timestamp_seconds"
                ],

            "blur_score":
                blur_data.get(
                    "blur_score"
                ),

            "brightness":
                blur_data.get(
                    "brightness"
                ),

            "accepted":
                blur_data.get(
                    "accepted",
                    False
                ),

            "state":
                blur_data.get(
                    "state",
                    "unreadable"
                ),

            "selected_keyframe":
                selected,

            "difference_score":
                difference_score
        }

        frame_metadata_rows.append(
            frame_row
        )

        if selected:

            manifest_row = {
                "keyframe_id":
                    keyframe_id,

                "filename":
                    filename,

                "source_frame_index":
                    record[
                        "source_frame_index"
                    ],

                "timestamp_seconds":
                    record[
                        "timestamp_seconds"
                    ],

                "blur_score":
                    blur_data.get(
                        "blur_score"
                    ),

                "difference_score":
                    difference_score
            }

            keyframe_manifest_rows.append(
                manifest_row
            )

            keyframe_id += 1

    # --------------------------------------------------------
    # 7. FRAME METADATA CSV
    # --------------------------------------------------------

    frame_metadata_path = (
        output_root /
        "frame_metadata.csv"
    )

    _write_csv(
        frame_metadata_path,
        frame_metadata_rows,
        [
            "filename",
            "source_frame_index",
            "timestamp_seconds",
            "blur_score",
            "brightness",
            "accepted",
            "state",
            "selected_keyframe",
            "difference_score"
        ]
    )

    # --------------------------------------------------------
    # 8. KEYFRAME MANIFEST
    # --------------------------------------------------------

    keyframes_manifest_path = (
        output_root /
        "keyframes_manifest.csv"
    )

    _write_csv(
        keyframes_manifest_path,
        keyframe_manifest_rows,
        [
            "keyframe_id",
            "filename",
            "source_frame_index",
            "timestamp_seconds",
            "blur_score",
            "difference_score"
        ]
    )

    # --------------------------------------------------------
    # 9. QUALITY REPORT
    # --------------------------------------------------------

    blur_scores = [
        row["blur_score"]
        for row
        in frame_metadata_rows
        if row["blur_score"]
        is not None
    ]

    usable_frames = sum(
        1
        for row
        in frame_metadata_rows
        if row["accepted"]
    )

    blur_rejected = (
        len(frame_metadata_rows)
        - usable_frames
    )

    selected_keyframes = (
        len(
            keyframe_manifest_rows
        )
    )

    redundant_skipped = (
        len(frame_metadata_rows)
        - selected_keyframes
    )

    if frame_metadata_rows:

        retention_percentage = (
            selected_keyframes
            / len(frame_metadata_rows)
            * 100.0
        )

    else:

        retention_percentage = 0.0

    quality_report = {
        "source_frames":
            video_metadata[
                "source_frame_count"
            ],

        "extracted_frames":
            len(frame_metadata_rows),

        "usable_frames":
            usable_frames,

        "blur_rejected":
            blur_rejected,

        "selected_keyframes":
            selected_keyframes,

        "redundant_skipped":
            redundant_skipped,

        "retention_percentage":
            retention_percentage,

        "minimum_blur_score":
            min(blur_scores)
            if blur_scores
            else None,

        "maximum_blur_score":
            max(blur_scores)
            if blur_scores
            else None,

        "mean_blur_score":
            (
                sum(blur_scores)
                / len(blur_scores)
            )
            if blur_scores
            else None,

        "sample_fps":
            sample_fps,

        "blur_threshold":
            blur_threshold,

        "difference_threshold":
            difference_threshold
    }

    quality_report_path = (
        output_root /
        "quality_report.json"
    )

    with quality_report_path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            quality_report,
            file,
            indent=2
        )

    # --------------------------------------------------------
    # RETURN INTEGRATION INFORMATION
    # --------------------------------------------------------

    return {
        "video_metadata":
            video_metadata,

        "quality_report":
            quality_report,

        "video_metadata_path":
            str(
                video_metadata_path
            ),

        "frame_metadata_path":
            str(
                frame_metadata_path
            ),

        "keyframes_manifest_path":
            str(
                keyframes_manifest_path
            ),

        "quality_report_path":
            str(
                quality_report_path
            ),

        "keyframes_dir":
            str(
                keyframes_folder
            ),

        "stabilized_frames_dir":
            (
                str(stabilized_folder)
                if enable_stabilization
                else None
            )
    }