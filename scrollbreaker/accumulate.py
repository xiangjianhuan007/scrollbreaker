"""累积器：判定「这一屏和上一屏，到底是不是同一页」。

这是整个项目最核心的一块，也是最容易做错的一块。

反面教材（早期实现）：
    只看「两屏有几行重合」就拼。实测中，公众号文章和聊天窗口之间恰好
    重合了 6 行（都是「正常」「好的」这类短句），于是把一篇文章和一串
    车间对话拼成了一条记录——**数据污染了，而且看不出来**。

正确做法：四道闸门全部通过，才允许合并。

    ① 时间窗   两屏间隔 ≤ window_s（默认 180s）。再久就是「过了一会儿又看」
    ② 类型一致 两屏 page_type 相同，且都不是 mixed
    ③ 页头一致 页头锚点相同（article 例外：滚动时首行会变，同类型即认同一篇）
    ④ 有实质重合 完全相同行的数量 ≥ min_overlap（默认 2）

任一条不过 = 换页了 = 另起一条，绝不拼。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from .config import CompiledPatterns, Config, DEFAULT_CONFIG
from .pagetype import (
    ACCUMULABLE,
    ARTICLE,
    CHAT,
    MIXED,
    body_lines,
    chat_anchor,
    head_anchor,
    normalize,
    page_type,
)


class Mode(str, Enum):
    """这一条记录是怎么来的。"""

    ROLL = "roll"   # 与上一屏同页，合并而成
    NEW = "new"     # 换页了，独立成条


@dataclass
class Frame:
    """一屏采样。"""

    lines: Sequence[str]
    ts: float                      # 采样时间（秒，epoch）

    def __post_init__(self):
        self.lines = list(self.lines)


@dataclass
class Merge:
    """一次 push 的结果。"""

    mode: Mode
    lines: list[str]
    page: str                 # 页面类型
    anchor: str               # 页头锚点
    overlap: int              # 与上一屏的重合行数
    scene: str                # "<page>|<anchor>"，同一 scene 才是同一次阅读
    text: str                 # 最终文本（已按 max_text_chars 截断）
    gate_log: dict = field(default_factory=dict)   # 每道闸门的判定结果，便于排查

    @property
    def line_count(self) -> int:
        return len(self.lines)


def _same_page(
    prev: dict, ptype: str, phead: str, overlap: int, cur_ts: float, cfg: Config
) -> tuple[bool, dict]:
    """四道闸门。返回 (是否同页, 逐闸trace)。"""
    prev_lines = prev.get("lines") or []
    prev_type = prev.get("type") or ""
    prev_head = prev.get("head") or ""
    prev_ts = float(prev.get("ts") or 0.0)

    g1_time = bool(prev_lines) and (cur_ts - prev_ts) <= cfg.window_s
    g2_type = prev_type == ptype and prev_type != MIXED and ptype != MIXED
    g3_head = prev_head == phead
    g4_overlap = overlap >= cfg.min_overlap

    # 文章页滚动时首行会变（标题滚出屏幕），靠「类型=article」认同一篇
    g3_pass = True if ptype == ARTICLE else g3_head

    ok = g1_time and g2_type and g3_pass and g4_overlap
    trace = {
        "time_window": g1_time,
        "same_type": g2_type,
        "same_anchor": g3_head,
        "anchor_relaxed": ptype == ARTICLE,
        "overlap_enough": g4_overlap,
    }
    return ok, trace


class Accumulator:
    """有状态的累积器：喂进一屏一屏的文本，吐出「该不该合并」。

    用法：
        acc = Accumulator()
        for snap in snapshots:            # 每 N 秒一屏
            m = acc.push(Frame(lines=snap.lines, ts=snap.ts))
            if m.mode is Mode.ROLL:       # 同一页在滚动，用 m.text（完整累积）
                ...
            else:                          # 换页了，m.text 是这一页的第一屏
                ...
    """

    def __init__(self, cfg: Config = DEFAULT_CONFIG):
        self.cfg = cfg
        self.pats: CompiledPatterns = cfg.compiled()
        self._prev: dict = {}
        self._last_norm: str | None = None

    # ── 状态 ────────────────────────────────────────────────
    @property
    def current_lines(self) -> list[str]:
        return list(self._prev.get("lines") or [])

    @property
    def current_page(self) -> str:
        return str(self._prev.get("type") or "")

    def reset(self) -> None:
        self._prev = {}
        self._last_norm = None

    # ── 主流程 ──────────────────────────────────────────────
    def push(self, frame: Frame) -> Merge:
        keep = [l for l in frame.lines if l.strip()]
        ptype = page_type(keep, self.cfg, self.pats)
        # 聊天页用发言人集合做锚点（页头可能已滚出屏幕），其余用首行
        if ptype == CHAT:
            phead = chat_anchor(keep, self.cfg, self.pats)
        else:
            phead = head_anchor(keep, self.cfg, self.pats)

        prev = self._prev
        # 重合判定必须基于「上一帧真实观测到的行」（raw），不能用已剥横幅的输出版本，
        # 否则文章页剥掉顶部几行后，下一帧就再也算不出重合，会误判成换页。
        prev_observed = [str(x) for x in (prev.get("raw") or prev.get("lines") or [])]
        prev_lines = [str(x) for x in (prev.get("lines") or [])]
        overlap = len(set(keep) & set(prev_observed))

        same, trace = _same_page(prev, ptype, phead, overlap, frame.ts, self.cfg)

        if same:
            # 文章页要剥掉顶部的消息横幅，否则正文里夹一句聊天
            incoming = body_lines(keep, self.cfg) if ptype == ARTICLE else keep
            merged = list(prev_lines)
            seen = set(merged)
            for line in incoming:
                if line not in seen:      # 保序去重
                    merged.append(line)
                    seen.add(line)
            if len(merged) > self.cfg.max_lines:
                merged = merged[-self.cfg.max_lines:]
            mode = Mode.ROLL
        else:
            # 新起一条时，文章页同样要剥掉顶部横幅——否则「在吗」就混进正文了
            base = body_lines(keep, self.cfg) if ptype == ARTICLE else keep
            merged = list(base)[-self.cfg.max_lines:]
            mode = Mode.NEW

        self._prev = {
            "lines": merged,
            "raw": list(keep),          # 本帧原始观测行，用于下一帧的重合判定
            "ts": frame.ts,
            "type": ptype,
            "head": phead,
        }

        text = "\n".join(merged)[: self.cfg.max_text_chars]
        return Merge(
            mode=mode,
            lines=merged,
            page=ptype,
            anchor=phead,
            overlap=overlap,
            scene=f"{ptype}|{phead}",
            text=text,
            gate_log=trace,
        )

    def push_text(self, raw_text: str, ts: float, splitter=None) -> Merge:
        """便捷入口：直接喂 OCR 后的整段文本。"""
        lines = splitter(raw_text) if splitter else [l.strip() for l in raw_text.splitlines() if l.strip()]
        return self.push(Frame(lines=lines, ts=ts))

    # ── 文本层去重（配合 dedup.Deduper） ──────────────────
    def is_text_unchanged(self, merge: Merge) -> bool:
        """整段归一化后与上次完全一致 → 内容没变，不必重复上报。"""
        n = normalize(merge.text, self.cfg)
        unchanged = (n == self._last_norm) or (n == "")
        self._last_norm = n
        return unchanged
