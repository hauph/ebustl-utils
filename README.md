# ebustl-utils

A Python library for working with EBU STL (European Broadcasting Union Subtitling) files. Extract teletext subtitles from MXF video files and read/parse EBU STL subtitle files with formatting support.

## Features

- **STLExtractor** — Extract teletext/OP-47 subtitles from MXF video files and convert to EBU STL format.
- **STLReader** — Read and parse EBU STL (.stl) binary files into structured caption data.
- Support EBU Tech 3264-E specification.
- Preserves formatting: colors, italic, bold, underline, double-height, flash.
- **Inline styling support** — Detects multiple styles within a single caption (e.g., multi-colored text).
- **Adobe Premiere compatible** — Follows Teletext conventions for color reset on newlines.
- Layout information: vertical positioning, text justification.
- Multiple character code tables (Latin, Cyrillic, Arabic, Greek, Hebrew).
- Accurate timecode handling with frame rate detection.
- Lenient parsing with validation warnings for malformed files.

## Requirements

- Python 3.8+ (recommended: 3.11).
- `ffmpeg` and `ffprobe` (required for MXF extraction).

## Installation

<!-- ```bash
pip install ebustl-utils
``` -->

Install with `pip install .` or install in editable mode with `pip install -e .` to allow you to edit the source without needing to re-install.

## Quick Start

### Extract Subtitles from MXF

```python
from ebustl_utils import STLExtractor

# Extract teletext subtitles from MXF and save as EBU STL
# Output file is automatically named after the MXF (eg: video.mxf -> video.stl)
extractor = STLExtractor(
    mxf_path="input_path/video.mxf",
    output_dir="output_path/"
)
extractor.extract()
# Creates: output_path/video.stl
```

### Read an EBU STL File

```python
from ebustl_utils import STLReader

# Read and parse an STL file
with open("subtitles.stl", "rb") as f:
    raw_data = f.read()

reader = STLReader()
reader.read(raw_data)

# Access parsed data
for caption in reader.captions:
    print(f"{caption.start_timecode} --> {caption.end_timecode}")
    print(caption.text)
    ...
```

## API Reference

### STLExtractor

Extracts teletext data from MXF files with embedded OP-47/VANC subtitle streams.

```python
STLExtractor(mxf_path: str, output_dir: str)
```

**Parameters:**

- `mxf_path` — Path to the input MXF file.
- `output_dir` — Directory for the output STL file (filename derived from MXF).

**Methods:**

- `extract()` — Perform the extraction and save to the output directory.

**Example:**

```python
from ebustl_utils import STLExtractor

extractor = STLExtractor("broadcast.mxf", "output/")
extractor.extract()

print(f"Output: {extractor.output_path}")  # output/broadcast.stl
```

### STLReader

Reads EBU STL binary files and extracts caption data with timing and formatting.

```python
STLReader(fps_override: Optional[float] = None)
```

**Parameters:**

- `fps_override` — Optional frame rate to use instead of auto-detection from GSI block.

**Properties:**

- `captions` — List of `STLCaption` objects with timing, text, and formatting.
- `fps` — Detected or overridden frame rate.
- `language` — Language code from GSI block.
- `gsi` — Full GSI (General Subtitle Information) block data.
- `result` — Original decode result.

**Methods:**

- `read(raw: bytes)` — Parse raw STL file bytes.

**Caption Data Structure:**

Each caption contains:

```python
{
    "start": 0,                       # Start time in microseconds
    "start_timecode": "00:00:00;00",  # SMPTE timecode format
    "end": 2500000,                   # End time in microseconds
    "end_timecode": "00:00:02;12",    # SMPTE timecode format
    "text": "Caption text",           # Decoded text content
    "style": {                        # CSS-like styling (None if default/not available)
        "color": "yellow",            # Foreground color
        "background-color": "black",  # Background color (boxing)
        "font-style": "italic",
        "font-weight": "bold",
        "text-decoration": "underline",
        "visibility": "flash",        # Flashing text
        "line-height": "double",      # Double-height text
    },
    "layout": {                       # Positioning (None if default/not available)
        "vertical_position": 20,      # Row 0-23
        "text_align": "center",       # left, center, right
    },
    "segments": [...]                 # Inline styled segments (see below)
}
```

**Inline Styled Segments:**

When a caption contains multiple inline styles (e.g., different colors for different words), the `segments` field provides granular styling information:

```python
{
    "text": "blue green\nHello world",
    "style": None,                    # None when segments are present
    "segments": [
        {"text": "blue ", "style": {"color": "blue"}},
        {"text": "green\n", "style": {"color": "green"}},
        {"text": "Hello world"}       # No style = default (white)
    ]
}
```

- The `segments` field is only present when there are **multiple inline styles** within a caption.
- Each segment contains its own `text` and optional `style` dictionary.
- For single-style captions, use the top-level `style` field (segments will be absent).
- **Color resets on newlines** — Following Teletext conventions and Adobe Premiere behavior, foreground color resets to white at the start of each new line.

**Example:**

```python
from ebustl_utils import STLReader

reader = STLReader()

with open("subtitles.stl", "rb") as f:
    raw_data = f.read()
    reader.read(raw_data)

print(f"Language: {reader.language}")
print(f"Frame rate: {reader.fps} fps")
print(f"Total captions: {len(reader.captions)}")

for caption in reader.captions:
    print(f"\n[{caption['start_timecode']}] {caption['text']}")
    
    # Check for inline styled segments (multi-color text, etc.)
    if caption.get('segments'):
        for seg in caption['segments']:
            style = seg.get('style', {})
            color = style.get('color', 'white')
            print(f"  '{seg['text']}' -> {color}")
    
    # Single-style caption
    elif caption.get('style'):
        print(f"  Style: {caption['style']}")
```

### Validation Warnings

STLReader uses lenient parsing — it reads TTI blocks until EOF and tolerates minor metadata inconsistencies. This allows it to successfully parse files that strict parsers like Adobe Premiere would reject.

When structural issues are detected (such as invalid EBN/CS field combinations in TTI blocks), a `STLValidationWarning` is emitted:

``` python
STLValidationWarning: STL file validation issues: 3 of first 9 TTI block(s) have 
intermediate EBN (1-254) with invalid CS=0. This file may fail in strict parsers 
like Adobe Premiere. Parsed 9 captions successfully.
```

**Suppress warnings** (if you don't need them):

```python
import warnings
from ebustl_utils.STLReader import STLReader, STLValidationWarning

warnings.filterwarnings('ignore', category=STLValidationWarning)
reader = STLReader()
reader.read(data)  # No warning displayed
```

**Treat as error** (strict mode):

```python
import warnings
from ebustl_utils.STLReader import STLReader, STLValidationWarning

warnings.filterwarnings('error', category=STLValidationWarning)
reader.read(data)  # Raises STLValidationWarning exception on mismatch
```

## Development

### Setup

```bash
git clone https://github.com/hauph/ebustl-utils.git
cd ebustl-utils
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

Or build the Docker image which includes `ffmpeg`, `ffprobe` and `ebustl-utils`:

```bash
docker build -t ebustl_utils .
docker run --rm -v "$(pwd)":/app ebustl_utils python dev.py
```

### Running Tests (recommended inside a [virtual environment](https://www.w3schools.com/django/django_create_virtual_environment.php))

```bash
pytest
```

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [EBU Tech 3264-E](https://tech.ebu.ch/docs/tech/tech3264.pdf) — EBU Subtitling Data Exchange Format specification
- [teletext-decoder](https://github.com/ZXGuesser/teletext-decoder) — Teletext packet decoding
