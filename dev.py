"""
Development script for running MXF to STL conversion.

Usage:
    Simply run: python dev.py

This will convert the sample MXF files to STL format.
"""

import sys
import os
import json

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

        # Output STL file with same name
        stl_file = os.path.splitext(mxf_file)[0] + ".stl"
        stl_path = os.path.join(output_dir, stl_file)

        print(f"\n{'=' * 60}")
        print(f"Processing: {mxf_file}")
        print(f"Output: {stl_path}")
        print(f"{'=' * 60}")

        try:
            # Convert MXF to STL (extracts ALL teletext pages)
            extractor = STLExtractor(mxf_path, stl_path)
            extractor.extract()
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
                reader.read(raw_data)
                captions = reader.captions
                print(f"File: {stl_file}")
                print(json.dumps(captions, indent=4))
                print(f"{'=' * 60}")
        except Exception as e:
            print(f"\n✗ Error reading {stl_file}: {e}")


def main():
    extract_stl()
    read_stl()


if __name__ == "__main__":
    main()
