import argparse

from preprocessing import analyze_blur


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("input_folder")
    parser.add_argument("output_folder")

    args = parser.parse_args()

    scores = analyze_blur(
        args.input_folder,
        args.output_folder
    )

    print()
    print("==============================")
    print("10 LOWEST-SCORING FRAMES")
    print("==============================")

    for filename, score in scores[:10]:
        print(
            filename,
            "Score:",
            round(score, 2)
        )

    print()
    print("==============================")
    print("10 HIGHEST-SCORING FRAMES")
    print("==============================")

    for filename, score in scores[-10:]:
        print(
            filename,
            "Score:",
            round(score, 2)
        )

    print()
    print("Lowest-scoring frames copied to:")
    print(args.output_folder)


if __name__ == "__main__":
    main()