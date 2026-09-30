import argparse

from preprocessing import detect_blur


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("input_folder")
    parser.add_argument("good_folder")
    parser.add_argument("blurry_folder")

    parser.add_argument(
        "--blur-threshold",
        type=float,
        default=100.0
    )

    args = parser.parse_args()

    results = detect_blur(
        args.input_folder,
        args.good_folder,
        args.blurry_folder,
        args.blur_threshold
    )

    good_count = sum(
        1
        for result in results.values()
        if result["accepted"]
    )

    blurry_count = len(results) - good_count

    print()
    print("================================")
    print("     BLUR DETECTION COMPLETE")
    print("================================")

    print("Threshold:", args.blur_threshold)
    print("Good frames:", good_count)
    print("Blurry frames:", blurry_count)
    print("Total:", len(results))


if __name__ == "__main__":
    main()