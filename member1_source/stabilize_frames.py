import argparse

from preprocessing import stabilize_frames


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("input_folder")
    parser.add_argument("output_folder")

    args = parser.parse_args()

    count = stabilize_frames(
        args.input_folder,
        args.output_folder
    )

    print()
    print("================================")
    print("     STABILIZATION COMPLETE")
    print("================================")

    print("Input frames:", count)
    print("Output folder:", args.output_folder)


if __name__ == "__main__":
    main()