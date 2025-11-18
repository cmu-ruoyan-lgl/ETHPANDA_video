#!/usr/bin/env python3
import argparse
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


TIME_LINE_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}\s*$")
INDEX_LINE_RE = re.compile(r"^\d+\s*$")
GLOSS_LINE_RE = re.compile(r'"\s*([^"]+?)\s*"\s*->\s*"\s*([^"]+?)\s*"')

# Use rare characters for placeholders to minimize collisions with natural text.
PLACEHOLDER_PREFIX = "⟦G"
PLACEHOLDER_SUFFIX = "⟧"


def iterate_blocks(lines: Iterable[str]) -> Iterable[List[str]]:
    block: List[str] = []
    for line in lines:
        block.append(line)
        if line.strip() == "":
            yield block
            block = []
    if block:
        yield block


def parse_glossary(glossary_path: Path) -> List[Tuple[str, str]]:
    if not glossary_path.exists():
        return []
    pairs: List[Tuple[str, str]] = []
    with glossary_path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            m = GLOSS_LINE_RE.search(raw)
            if not m:
                continue
            src = m.group(1).strip()
            dst = m.group(2).strip()
            if not src or not dst:
                continue
            pairs.append((src, dst))
    # Sort by source length desc to match longer phrases first (e.g., "ZK Rollup" before "Rollup")
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def build_placeholder_text(text: str, glossary_pairs: List[Tuple[str, str]]) -> Tuple[str, Dict[str, str]]:
    """
    Replace glossary English terms in `text` with unique placeholders.
    Returns (text_with_placeholders, placeholder_to_cn_map).
    """
    placeholder_map: Dict[str, str] = {}
    protected = text
    for idx, (src_en, dst_cn) in enumerate(glossary_pairs):
        if not src_en:
            continue
        # Compile a case-insensitive regex for the exact source phrase.
        # Avoid using word boundaries because many terms include symbols/spaces.
        pat = re.compile(re.escape(src_en), re.IGNORECASE)
        placeholder = f"{PLACEHOLDER_PREFIX}{idx}{PLACEHOLDER_SUFFIX}"
        if pat.search(protected):
            protected = pat.sub(placeholder, protected)
            placeholder_map[placeholder] = dst_cn
    return protected, placeholder_map


def restore_placeholders(chinese_text: str, placeholder_map: Dict[str, str]) -> str:
    restored = chinese_text
    # Replace placeholders with their intended Chinese translations
    for placeholder, cn in placeholder_map.items():
        restored = restored.replace(placeholder, cn)
    return restored


def normalize_chinese_spacing(text: str) -> str:
    # Remove extra spaces
    text = re.sub(r"\s{2,}", " ", text)
    # Remove spaces before Chinese punctuation
    text = re.sub(r"\s+([，。！？：；、（）；「」『』——])", r"\1", text)
    # Replace three dots with ellipsis
    text = re.sub(r"([^\d])\s*\.\.\.", r"\1…", text)
    return text.strip()


def collect_srt_files(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted([p for p in input_path.glob("*.srt") if p.is_file()])


def make_output_path(src: Path, output_dir: Path, overwrite: bool) -> Path:
    if overwrite:
        return src
    return output_dir / src.name


class Translator:
    def translate(self, text: str) -> str:
        raise NotImplementedError


class OpenAITranslator(Translator):
    def __init__(self, model: str):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY 未设置。请先 export OPENAI_API_KEY=你的key")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:
            raise RuntimeError("缺少 openai 依赖，请先安装：pip install openai>=1.51.0") from e
        self._client = OpenAI(api_key=self.api_key)

    def translate(self, text: str) -> str:
        """
        Translate English `text` to Simplified Chinese. Preserve placeholders like ⟦G0⟧.
        """
        prompt = (
            "将以下英文内容翻译为简体中文，要求：\n"
            "1) 保留形如“⟦G数字⟧”的占位符原样不变；\n"
            "2) 用准确、自然的中文表达，不要逐词直译；\n"
            "3) 不要输出与翻译无关的解释或引号；\n"
            "4) 如遇专有名词，保持其大小写/缩写一致；\n"
            "仅输出翻译后的中文文本：\n\n"
            f"{text}"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是精通 Web3 术语的专业中英翻译。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            content = resp.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI 翻译失败：{e}")


def pick_translator(name: str, model: str) -> Translator:
    name = (name or "").lower()
    if name in ("openai", "gpt"):
        return OpenAITranslator(model=model)
    raise RuntimeError("未指定可用的翻译器。请使用 --translator openai 并设置 OPENAI_API_KEY")


def combine_text_lines(block: List[str]) -> str:
    text_lines: List[str] = []
    for line in block:
        if TIME_LINE_RE.match(line) or INDEX_LINE_RE.match(line) or line.strip() == "":
            continue
        text_lines.append(line.rstrip("\n"))
    combined = " ".join(s.strip() for s in text_lines if s.strip())
    # Collapse multiple spaces
    combined = re.sub(r"\s{2,}", " ", combined).strip()
    return combined


def process_block_to_bilingual(block: List[str], glossary_pairs: List[Tuple[str, str]], translator: Translator) -> List[str]:
    if not block:
        return block

    # Extract index/time lines and reconstruct later
    index_line = None
    time_line = None
    for line in block:
        if index_line is None and INDEX_LINE_RE.match(line):
            index_line = line
            continue
        if time_line is None and TIME_LINE_RE.match(line):
            time_line = line
            continue
    if index_line is None or time_line is None:
        # Not a valid SRT block; return as-is
        return block

    english_text = combine_text_lines(block)
    if not english_text:
        return block

    # Protect terms with placeholders before translation
    protected_text, placeholder_map = build_placeholder_text(english_text, glossary_pairs)
    chinese_raw = translator.translate(protected_text)
    chinese_text = normalize_chinese_spacing(restore_placeholders(chinese_raw, placeholder_map))

    out_block: List[str] = []
    out_block.append(index_line)
    out_block.append(time_line)
    out_block.append(chinese_text + "\n")
    out_block.append(english_text + "\n")
    out_block.append("\n")
    return out_block


def translate_file_to_bilingual(src: Path, dst: Path, glossary_pairs: List[Tuple[str, str]], translator: Translator) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    out_lines: List[str] = []
    for block in iterate_blocks(lines):
        processed = process_block_to_bilingual(block, glossary_pairs, translator)
        out_lines.extend(processed)

    with dst.open("w", encoding="utf-8") as w:
        w.writelines(out_lines)


def main():
    repo_root = Path(__file__).resolve().parents[1]
    default_gloss = repo_root / "docs" / "WEB3专有名词翻译.md"

    parser = argparse.ArgumentParser(
        description="将英文 SRT 转换为中英对照 SRT：保留编号与时间轴，文本行生成“中文+英文”两行。"
    )
    parser.add_argument(
        "--input",
        "-i",
        help="输入文件或目录（缺省：./subtitles_en_optimized）",
        default="subtitles_en_optimized",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        help="输出目录（缺省：./subtitles_bilingual），若 --overwrite 则忽略。",
        default="subtitles_bilingual",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="原位覆盖输入文件（谨慎使用）。",
    )
    parser.add_argument(
        "--translator",
        choices=["openai"],
        default="openai",
        help="翻译后端。当前支持：openai",
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-4o-mini",
        help="OpenAI 模型名称（默认：gpt-4o-mini）",
    )
    parser.add_argument(
        "--glossary",
        help=f"术语表路径（默认：{default_gloss}）",
        default=str(default_gloss),
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    glossary_path = Path(args.glossary).expanduser().resolve()

    files = collect_srt_files(input_path)
    if not files:
        raise SystemExit(f"未找到 .srt 文件：{input_path}")

    glossary_pairs = parse_glossary(glossary_path)
    translator = pick_translator(args.translator, model=args.openai_model)

    if not args.overwrite:
        output_dir.mkdir(parents=True, exist_ok=True)

    for src in files:
        dst = make_output_path(src, output_dir, args.overwrite)
        translate_file_to_bilingual(src, dst, glossary_pairs, translator)
        print(f"Bilingual: {src.name} -> {dst}")


if __name__ == "__main__":
    main()


