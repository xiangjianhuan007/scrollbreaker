"""命令行入口。

两个常用子命令：

  replay   拿一段「多帧文本」的 JSONL 离线跑分页逻辑，验证你的参数
           （不用真截屏，最适合调阈值 / 写回归）

  watch    真的去截屏 + OCR + 累积，把结果追加到 jsonl

watch 在 Windows/macOS 上都能用（依赖 mss），但你要自己保证被采集的窗口
在前台 —— 本项目只负责「看图说话」，不负责把窗口调出来。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .accumulate import Accumulator, Frame, Mode
from .config import Config
from .dedup import Deduper, is_blank
from .ocr import CmdOCR, NullOCR


def _cfg_from_args(a) -> Config:
    cfg = Config()
    if a.window_s is not None:
        cfg.window_s = a.window_s
    if a.max_lines is not None:
        cfg.max_lines = a.max_lines
    if a.min_overlap is not None:
        cfg.min_overlap = a.min_overlap
    return cfg


def cmd_replay(a) -> int:
    """离线回放：每行一个 JSON，形如 {"ts": 1000.0, "lines": ["...", "..."]}。"""
    cfg = _cfg_from_args(a)
    acc = Accumulator(cfg)
    n_roll = n_new = 0
    with open(a.input, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[跳过] 第 {lineno} 行不是合法 JSON: {e}", file=sys.stderr)
                continue
            frame = Frame(lines=rec.get("lines") or [], ts=float(rec.get("ts") or lineno))
            m = acc.push(frame)
            n_roll += m.mode is Mode.ROLL
            n_new += m.mode is Mode.NEW
            print(
                json.dumps(
                    {
                        "frame": lineno,
                        "mode": m.mode.value,
                        "page": m.page,
                        "anchor": m.anchor,
                        "overlap": m.overlap,
                        "lines": m.line_count,
                        "gate": m.gate_log,
                    },
                    ensure_ascii=False,
                )
            )
    print(f"\n合计 {n_new} 条新页 / {n_roll} 次合并", file=sys.stderr)
    return 0


def cmd_watch(a) -> int:
    """真截屏循环。"""
    try:
        import mss  # noqa: F401
        from PIL import Image
    except ImportError:
        print("watch 需要 mss 和 Pillow：pip install mss pillow", file=sys.stderr)
        return 2

    import io
    import mss

    cfg = _cfg_from_args(a)
    ocr = CmdOCR(a.ocr_cmd) if a.ocr_cmd else NullOCR()
    acc = Accumulator(cfg)
    ded = Deduper(cfg)
    out = open(a.output, "a", encoding="utf-8")
    sct = mss.mss()
    mon = sct.monitors[a.monitor]
    print(f"采集区域 {mon}，间隔 {a.interval}s，输出 {a.output}", file=sys.stderr)

    try:
        while True:
            shot = sct.grab(mon)
            buf = io.BytesIO()
            Image.frombytes("RGB", shot.size, shot.rgb).save(buf, format="PNG")
            png = buf.getvalue()

            blank, mean, std = is_blank(png, cfg)
            if blank:
                time.sleep(a.interval)
                continue

            dup, _h = ded.seen_pixels(png)
            if dup:
                time.sleep(a.interval)
                continue

            text = ocr.read(png)
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if not lines:
                time.sleep(a.interval)
                continue

            m = acc.push(Frame(lines=lines, ts=time.time()))
            if not acc.is_text_unchanged(m):
                rec = {
                    "ts": time.time(),
                    "mode": m.mode.value,
                    "page": m.page,
                    "anchor": m.anchor,
                    "scene": m.scene,
                    "overlap": m.overlap,
                    "text": m.text,
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[{m.mode.value}] {m.page}/{m.anchor} {m.line_count} 行", file=sys.stderr)
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\n停止。", file=sys.stderr)
    finally:
        out.close()
        sct.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scrollbreaker", description="把滚动的屏幕切成能读的页")
    p.add_argument("--version", action="version", version="scrollbreaker 0.1.0")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, help_text in (("replay", "离线回放多帧文本"), ("watch", "实时截屏采集")):
        s = sub.add_parser(name, help=help_text)
        s.add_argument("--window-s", type=float, default=None, help="同一次阅读的时间窗（秒）")
        s.add_argument("--max-lines", type=int, default=None, help="单次累积行数上限")
        s.add_argument("--min-overlap", type=int, default=None, help="认定同页所需最小重合行数")
        if name == "replay":
            s.add_argument("input", help="JSONL：每行 {\"ts\":..., \"lines\":[...]}")
            s.set_defaults(func=cmd_replay)
        else:
            s.add_argument("--interval", type=float, default=20.0, help="截屏间隔（秒）")
            s.add_argument("--monitor", type=int, default=1, help="显示器编号（mss）")
            s.add_argument("--output", default="scrollbreaker.jsonl", help="输出 JSONL")
            s.add_argument("--ocr-cmd", nargs="+", default=None,
                           help="OCR 命令行，{img} 占位。如: --ocr-cmd tesseract {img} stdout -l chi_sim+eng --psm 6")
            s.set_defaults(func=cmd_watch)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
