import argparse

from preprocessing import inspect_video


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "video_path"
    )

    args = parser.parse_args()

    metadata = inspect_video(
        args.video_path
    )

    print()
    print("--- VIDEO INFORMATION ---")

    print(
        "Resolution:",
        metadata["width"],
        "x",
        metadata["height"]
    )

    print(
        "FPS:",
        round(metadata["fps"], 2)
    )

    print(
        "Total Frames:",
        metadata["source_frame_count"]
    )

    print(
        "Duration:",
        round(metadata["duration_seconds"], 2),
        "seconds"
    )

    print(
        "Codec:",
        metadata["codec"]
    )


if __name__ == "__main__":
    main()