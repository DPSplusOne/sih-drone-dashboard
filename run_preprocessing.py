from member1_source.preprocessing import run_preprocessing


def main():

    result = run_preprocessing(
        video_path="data/raw/drone_video.mp4",
        output_root="outputs/member1",
        sample_fps=2.0,
        blur_threshold=100.0,
        difference_threshold=12.0,
        enable_stabilization=False
    )

    report = result["quality_report"]

    print()
    print("====================================")
    print(" MEMBER 1 PREPROCESSING COMPLETE")
    print("====================================")

    print(
        "Source frames:",
        report["source_frames"]
    )

    print(
        "Extracted frames:",
        report["extracted_frames"]
    )

    print(
        "Usable frames:",
        report["usable_frames"]
    )

    print(
        "Blur rejected:",
        report["blur_rejected"]
    )

    print(
        "Selected keyframes:",
        report["selected_keyframes"]
    )

    print(
        "Redundant skipped:",
        report["redundant_skipped"]
    )

    print(
        "Retention:",
        round(
            report["retention_percentage"],
            2
        ),
        "%"
    )

    print()
    print(
        "Keyframes:",
        result["keyframes_dir"]
    )


if __name__ == "__main__":
    main()