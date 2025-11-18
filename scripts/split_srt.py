#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import List
import os


def read_srt_blocks(srt_path: Path, encoding: str = "utf-8") -> List[List[str]]:
    """
    Read an SRT file and return a list of blocks.
    Each block is a list of lines (including the trailing blank line if present).
    Blocks are separated by empty lines.
    """
    with srt_path.open("r", encoding=encoding, errors="replace") as f:
        lines = f.readlines()

    blocks: List[List[str]] = []
    current: List[str] = []

    for line in lines:
        current.append(line)
        if line.strip() == "":
            blocks.append(current)
            current = []

    if current:
        # Last block without trailing blank line
        blocks.append(current)

    return blocks


def write_chunks(
    blocks: List[List[str]],
    output_dir: Path,
    base_name: str,
    max_lines: int,
) -> List[Path]:
    """
    Write blocks into multiple SRT files such that each file has at most max_lines lines.
    Splitting occurs only on block boundaries. Original content is preserved.
    Returns a list of written file paths.
    """
    chunks: List[List[List[str]]] = []
    current_chunk: List[List[str]] = []
    current_lines = 0

    for block in blocks:
        block_line_count = len(block)
        # If adding this block would exceed the limit, start a new chunk (unless current is empty)
        if current_chunk and current_lines + block_line_count > max_lines:
            chunks.append(current_chunk)
            current_chunk = []
            current_lines = 0

        current_chunk.append(block)
        current_lines += block_line_count

    if current_chunk:
        chunks.append(current_chunk)

    # Determine zero-padding width for part numbers
    total_parts = max(1, len(chunks))
    pad_width = 2 if total_parts < 100 else 3 if total_parts < 1000 else 4

    output_dir.mkdir(parents=True, exist_ok=True)

    written_paths: List[Path] = []
    for idx, chunk in enumerate(chunks, start=1):
        part = f"part{idx:0{pad_width}d}"
        out_name = f"{base_name}.{part}.srt"
        out_path = output_dir / out_name
        with out_path.open("w", encoding="utf-8") as out_f:
            for block in chunk:
                out_f.writelines(block)
                # Do not force-add extra blank lines; preserve original
        written_paths.append(out_path)

    return written_paths


def main():
    parser = argparse.ArgumentParser(
        description="Split an SRT file into multiple files on block boundaries, "
        "limiting each output file to approximately N lines (including indices, timestamps, text, and blank lines)."
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to the input .srt file",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="subtitles",
        help="Directory to place split parts (default: subtitles)",
    )
    parser.add_argument(
        "--max-lines",
        "-n",
        type=int,
        default=600,
        help="Maximum lines per output file (default: 600). Splitting is block-safe.",
    )
    parser.add_argument(
        "--encoding",
        "-e",
        default="utf-8",
        help="Encoding to read input SRT (default: utf-8)",
    )

    args = parser.parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_dir = Path(args.output_dir).expanduser().resolve()

    # Build base name for output: keep all original stems except final extension
    # e.g., "file.en.srt" -> base_name "file.en"
    base_name = input_path.stem  # keeps ".en" when ".en.srt"

    blocks = read_srt_blocks(input_path, encoding=args.encoding)
    written = write_chunks(blocks, output_dir, base_name, max_lines=args.max_lines)

    # Print results to stdout for convenience
    print(f"Created {len(written)} files in: {output_dir}")
    for p in written:
        print(f"- {p.name}")


if __name__ == "__main__":
    # Improve macOS console legibility for non-ASCII filenames
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()


