#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from typing import Iterable, List, Tuple


TIME_LINE_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}\s*$")
INDEX_LINE_RE = re.compile(r"^\d+\s*$")

# Simple, conservative filler/disfluency patterns (standalone or punctuation-bounded).
FILLER_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?i)(^|\s)[-–—]?\s*um{1,}\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)[-–—]?\s*uh{1,}\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)[-–—]?\s*erm{0,}\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)[-–—]?\s*eh{1,}\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)[-–—]?\s*hmm{1,}\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)you know\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)i mean\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)kind of\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)sort of\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)basically\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)actually\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)literally\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)to be honest\b[ ,.\-…!?:;]*"),
    re.compile(r"(?i)(^|\s)honestly\b[ ,.\-…!?:;]*"),
    # Remove "like" only when clearly used as a filler (start-of-line or followed by punctuation/comma/dash)
    re.compile(r"(?i)(^|\s)[-–—]?\s*like(?=[ ,.\-…!?:;])"),
]

# Canonical Web3 terms mapping (case-insensitive whole-word replacements where safe).
TERM_REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\bweb3\b"), "Web3"),
    (re.compile(r"(?i)\bdefi\b"), "DeFi"),
    (re.compile(r"(?i)\bcefi\b"), "CeFi"),
    (re.compile(r"(?i)\bnft\b"), "NFT"),
    (re.compile(r"(?i)\bnfts\b"), "NFTs"),
    (re.compile(r"(?i)\bdao\b"), "DAO"),
    (re.compile(r"(?i)\bdaos\b"), "DAOs"),
    (re.compile(r"(?i)\bl1\b"), "L1"),
    (re.compile(r"(?i)\bl2\b"), "L2"),
    (re.compile(r"(?i)\blayer\s*2\b"), "Layer 2"),
    (re.compile(r"(?i)\blayer\s*1\b"), "Layer 1"),
    (re.compile(r"(?i)\bzk[-\s]?rollups?\b"), "ZK Rollups"),
    (re.compile(r"(?i)\bzk\b"), "ZK"),
    (re.compile(r"(?i)\bevm\b"), "EVM"),
    (re.compile(r"(?i)\bpos\b"), "PoS"),
    (re.compile(r"(?i)\bpow\b"), "PoW"),
    (re.compile(r"(?i)\bproof[-\s]?of[-\s]?stake\b"), "Proof of Stake"),
    (re.compile(r"(?i)\bproof[-\s]?of[-\s]?work\b"), "Proof of Work"),
    (re.compile(r"(?i)\bethereum\b"), "Ethereum"),
    (re.compile(r"(?i)\bbitcoin\b"), "Bitcoin"),
    (re.compile(r"(?i)\bsolana\b"), "Solana"),
    (re.compile(r"(?i)\bpolkadot\b"), "Polkadot"),
    (re.compile(r"(?i)\barbitrum\b"), "Arbitrum"),
    (re.compile(r"(?i)\boptimism\b"), "Optimism"),
    (re.compile(r"(?i)\bcosmos\b"), "Cosmos"),
    (re.compile(r"(?i)\btvl\b"), "TVL"),
    (re.compile(r"(?i)\btps\b"), "TPS"),
    (re.compile(r"(?i)\brwa(s)?\b"), r"RWA\1"),
    (re.compile(r"(?i)\blsd(s)?\b"), r"LSD\1"),
    (re.compile(r"(?i)\blst(s)?\b"), r"LST\1"),
    (re.compile(r"(?i)\busdt\b"), "USDT"),
    (re.compile(r"(?i)\busdc\b"), "USDC"),
]

# Punctuation/spacing normalization
SPACE_FIXES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\s{2,}"), " "),
    (re.compile(r"\s+([,.;:!?])"), r"\1"),
    (re.compile(r"([^\d])\s{0,}\.\.\."), r"\1…"),
    (re.compile(r"\s+—\s+"), " — "),
    (re.compile(r"\s+-\s+"), " - "),
]


def optimize_text_line(text: str) -> str:
    original = text
    # Remove filler/disfluencies
    for pat in FILLER_PATTERNS:
        text = pat.sub(" ", text)
    # Normalize spaces/punctuation
    for pat, repl in SPACE_FIXES:
        text = pat.sub(repl, text)
    text = text.strip()
    # Apply term replacements
    for pat, repl in TERM_REPLACEMENTS:
        text = pat.sub(repl, text)
    # Keep original casing if line is all caps (likely acronyms)
    if original.isupper():
        return text.upper()
    return text


def iterate_blocks(lines: Iterable[str]) -> Iterable[List[str]]:
    block: List[str] = []
    for line in lines:
        block.append(line)
        if line.strip() == "":
            yield block
            block = []
    if block:
        yield block


def process_block(block: List[str]) -> List[str]:
    if not block:
        return block
    out: List[str] = []
    for idx, line in enumerate(block):
        if idx == 0 and INDEX_LINE_RE.match(line):
            out.append(line)
            continue
        if idx <= 2 and TIME_LINE_RE.match(line):
            out.append(line)
            continue
        if TIME_LINE_RE.match(line):
            out.append(line)
            continue
        if INDEX_LINE_RE.match(line):
            out.append(line)
            continue
        if line.strip() == "":
            out.append(line)
            continue
        # Text line
        optimized = optimize_text_line(line.rstrip("\n"))
        out.append(optimized + "\n")
    return out


def optimize_srt_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    with dst.open("w", encoding="utf-8") as w:
        for block in iterate_blocks(lines):
            processed = process_block(block)
            w.writelines(processed)


def collect_srt_files(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    # directory
    return sorted([p for p in input_path.glob("*.srt") if p.is_file()])


def make_output_path(src: Path, output_dir: Path, overwrite: bool) -> Path:
    if overwrite:
        return src
    return output_dir / src.name


def main():
    parser = argparse.ArgumentParser(
        description="Optimize English SRT: remove filler/disfluencies and standardize Web3 terms while preserving indices and timestamps."
    )
    group = parser.add_mutually_exclusive_group(required=False)
    parser.add_argument(
        "--input",
        "-i",
        help="Input SRT file path OR directory containing SRT files (default: ./subtitles)",
        default="subtitles",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        help="Directory for optimized SRT files (default: ./subtitles_en_optimized). Ignored if --overwrite is set.",
        default="subtitles_en_optimized",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the original SRT files in place.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    files = collect_srt_files(input_path)
    if not files:
        raise SystemExit(f"No .srt files found under: {input_path}")

    if not args.overwrite:
        output_dir.mkdir(parents=True, exist_ok=True)

    for src in files:
        dst = make_output_path(src, output_dir, args.overwrite)
        optimize_srt_file(src, dst)
        print(f"Optimized: {src.name} -> {dst}")


if __name__ == "__main__":
    main()


