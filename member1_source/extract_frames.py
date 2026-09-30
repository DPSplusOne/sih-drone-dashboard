import argparse

from preprocessing import extract_frames


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "video_path"
    )

    parser.add_argument(
        "output_folder"
    )

    parser.add_argument(
        "--sample-fps",
        type=float,
        default=2.0
    )

    args = parser.parse_args()

    records = extract_frames(
        args.video_path,
        args.output_folder,
        args.sample_fps
    )

    print()
    print("--- FRAME EXTRACTION COMPLETE ---")

    print(
        "Frames saved:",
        len(records)
    )

    print(
        "Output folder:",
        args.output_folder
    )


if __name__ == "__main__":
    main()