"""所有可调参数集中在这里。

这些默认值不是拍脑袋来的，是在真实的长文阅读 + 群聊滚动场景里调出来的：

ROLL_WINDOW_S = 180
    同一次阅读最多算 3 分钟。再久就是「过了一会儿又看」，不该拼。

ROLL_MAX_LINES = 80
    一次累积最多 80 行。再多上下文就膨胀，模型也读不动。

ROLL_MIN_OVERLAP = 2
    至少 2 行完全一样，才认作「同一页在滚动」。1 行太容易误判——
    两个不同页面里都可能出现「好的」「。  

TIME_LIKE / STATUS_BAR
    状态栏（网速、电量、时间）每屏都在变，既不能当页头，也不能当重合证据。
"""

from dataclasses import dataclass, field
from typing import Pattern
import re


@dataclass
class Config:
    # ── 累积闸门 ──────────────────────────────────────────────
    window_s: float = 180.0        # 同一次阅读的时间窗（秒）
    max_lines: int = 80            # 单次累积行数上限
    min_overlap: int = 2           # 认定为「同一页」所需的最小重合行数

    # ── 静屏去重 ──────────────────────────────────────────────
    hash_bits: int = 64            # dHash 位数（64 = 8x8 差分）
    same_bits: int = 6             # 汉明距离 ≤ 此值视为同一屏（不重复上报）

    # ── 空白屏 ────────────────────────────────────────────────
    blank_mean: float = 12.0       # 平均亮度低于此值 → 黑屏
    blank_std: float = 3.0         # 亮度标准差低于此值 → 纯色屏

    # ── 页面类型判定 ──────────────────────────────────────────
    # 命中任一 → 认为这是「文章/长文」页（阅读类页面底部常驻这些按钮）
    article_patterns: list[str] = field(default_factory=lambda: [
        r"\+ ?关注", r"写留言", r"阅读原文", r"在看", r"点赞", r"分享到",
    ])
    # 命中任一 → 认为这是「列表/会话列表」页
    list_patterns: list[str] = field(default_factory=lambda: [
        r"\[图片\]", r"\[语音\]", r"\[视频\]", r"\[文件\]",
        r"折叠(的)?置顶", r"\[\d+条\]",
    ])
    # 命中 → 这是一行「发言人: 内容」的聊天
    chat_pattern: str = r"^\S{1,24}[:：]\s*\S"
    # 状态栏噪声行（网速/电量/时间），既不能当页头也不能当重合证据
    status_pattern: str = (
        r"^[\d\.\s]*(KB/S|M/s|MB/s|KB/s|G|%)?[\d\.\s]*$"
        r"|^\d{1,2}[:：]\d{2}$"
    )
    # 页头锚点保留长度：不同会话/不同文章前 N 个字通常就够区分
    anchor_len: int = 14
    # 文章页拼接时，前几行里找「第一行真正的正文」用的最小字数
    body_min_chars: int = 12
    body_scan_lines: int = 5
    # 横幅行上限字数：短于这个且不含文章控件特征的行，判为「顶部通知横幅」（"张三" / "在吗"）
    body_banner_max_chars: int = 8

    # ── 归一化 ────────────────────────────────────────────────
    # 整段文本归一化后与上一段相同 → 判为重复（只变了时间/电量）
    collapse_ws: bool = True
    max_text_chars: int = 4000

    def compiled(self) -> "CompiledPatterns":
        return CompiledPatterns(self)


@dataclass
class CompiledPatterns:
    article: "Pattern[str]"
    list_sig: "Pattern[str]"
    chat: "Pattern[str]"
    status: "Pattern[str]"

    def __init__(self, cfg: Config):
        joiner = "|"
        self.article = re.compile(joiner.join(cfg.article_patterns)) if cfg.article_patterns else None
        self.list_sig = re.compile(joiner.join(cfg.list_patterns)) if cfg.list_patterns else None
        self.chat = re.compile(cfg.chat_pattern)
        self.status = re.compile(cfg.status_pattern)


DEFAULT_CONFIG = Config()
