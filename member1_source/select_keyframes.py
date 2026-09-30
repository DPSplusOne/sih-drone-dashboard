import argparse

from preprocessing import select_keyframes


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("input_folder")
    parser.add_argument("output_folder")

    parser.add_argument(
        "--difference-threshold",
        type=float,
        default=12.0
    )

    args = parser.parse_args()

    results = select_keyframes(
        args.input_folder,
        args.output_folder,
        args.difference_threshold
    )

    selected_count = sum(
        1
        for result in results
        if result["selected"]
    )

    skipped_count = (
        len(results) - selected_count
    )

    print()
    print("================================")
    print("     KEYFRAME SELECTION COMPLETE")
    print("================================")

    print(
        "Input frames:",
        len(results)
    )

    print(
        "Selected keyframes:",
        selected_count
    )

    print(
        "Skipped frames:",
        skipped_count
    )

    if results:

        percentage = (
            selected_count
            / len(results)
            * 100
        )

        print(
            "Frames retained:",
            round(percentage, 2),
            "%"
        )


if __name__ == "__main__":
    main()