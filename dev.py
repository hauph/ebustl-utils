"""
Development script for running MXF to STL conversion.

Usage:
    Simply run: python dev.py

This will convert the sample MXF files to STL format.
"""

import sys
import os

# Add the project root to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from ebustl_utils import STLExtractor, STLReader


def extract_stl():
    # Sample MXF files in the samples folder
    samples_dir = os.path.join(os.path.dirname(__file__), "samples")
    output_dir = os.path.join(os.path.dirname(__file__), "output")

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # List of sample files to process
    mxf_files = [
        # Provide your own MXF files here
    ]

    for mxf_file in mxf_files:
        mxf_path = os.path.join(samples_dir, mxf_file)

        if not os.path.exists(mxf_path):
            print(f"File not found: {mxf_path}")
            continue

        print(f"\n{'=' * 60}")
        print(f"Processing: {mxf_file}")
        print(f"{'=' * 60}")

        try:
            # Convert MXF to STL (extracts ALL teletext pages)
            # STL file is automatically named after the MXF file
            extractor = STLExtractor(mxf_path, output_dir)
            extractor.extract()
            print(f"Output: {extractor.output_path}")
        except Exception as e:
            print(f"\n✗ Error processing {mxf_file}: {e}")


def read_stl():
    output_dir = os.path.join(os.path.dirname(__file__), "output")

    # List of sample files to process
    stl_files = [
        # Provide your own STL files here
    ]

    for stl_file in stl_files:
        stl_path = os.path.join(output_dir, stl_file)

        try:
            with open(stl_path, "rb") as f:
                raw_data = f.read()
                reader = STLReader()
                print(f"File: {stl_file}")
                reader.read(raw_data)
                print(f"Captions: {reader.captions}")
                # print(f"GSI: {reader.gsi}")
                # print(f"Language: {reader.language}")
                # print(f"FPS: {reader.fps}")
                print(f"{'=' * 60}")
        except Exception as e:
            print(f"\n✗ Error reading {stl_file}: {e}")


def main():
    extract_stl()
    read_stl()


if __name__ == "__main__":
    main()
