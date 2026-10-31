"""页面类型判定：这一屏到底是什么？

为什么必须先判类型：
    只看「两屏有没有重合行」是不够的。实测中，公众号文章和聊天窗口之间
    出现过 6 行完全相同的行（都是「正常」「好的」这类字），按重合拼就
    把一篇文章和一段聊天糊成了一条记录——数据彻底废掉。

所以先给每一屏定性，只有**同类型**的两屏才可能被拼到一起。
"""

import string
from typing import Iterable, Sequence

from .config import CompiledPatterns, Config, DEFAULT_CONFIG

# 页面类型
ARTICLE = "article"   # 文章/长文正文页
CHAT = "chat"         # 单聊/群聊会话页
LIST = "list"         # 会话列表 / 消息列表
TEXT = "text"         # 其他（设置页、纯文本、表单…）
MIXED = "mixed"       # 一屏里同时有文章特征和聊天/列表特征

#: 可以参与累积的类型。mixed 是「切换过程中的混合画面」，既不能当起点也不能被吸收。
ACCUMULABLE = (ARTICLE, CHAT, LIST, TEXT)


def page_type(lines: Sequence[str], cfg: Config = DEFAULT_CONFIG,
              pats: CompiledPatterns | None = None) -> str:
    """给一屏文本定性。

    Args:
        lines: 已按屏幕顺序切好的文本行
        cfg: 配置（阈值都在里面）
        pats: 预编译的正则（循环里复用，别每帧重编译）

    Returns:
        ARTICLE / CHAT / LIST / TEXT / MIXED
    """
    p = pats or cfg.compiled()
    chat = sum(1 for l in lines if p.chat.match(l))
    art = sum(1 for l in lines if p.article and p.article.search(l))
    lst = sum(1 for l in lines if p.list_sig and p.list_sig.search(l))

    # 同时具备两类特征 → 这屏本身就是切页中间态，判 mixed 单独处理
    if art and (chat >= 2 or lst >= 2):
        return MIXED
    if art:
        return ARTICLE
    if chat >= 2:
        return CHAT
    if lst:
        return LIST
    return TEXT


def head_anchor(lines: Sequence[str], cfg: Config = DEFAULT_CONFIG,
                pats: CompiledPatterns | None = None) -> str:
    """页头锚点：当前页的「身份」。

    聊天页的第一行通常是联系人名，文章页的第一行通常是标题，
    正文页的第一行通常是文章名。取它做锚点，锚点变了 = 换页了。

    尾部数字要剥掉：未读数是「张三 3」→「张三 12」，数字变了但人没变。
    """
    p = pats or cfg.compiled()
    for line in lines[:2]:
        s = line.strip()
        if not s or p.status.match(s):
            continue
        # 去掉尾部数字（未读数 / 计数）
        stripped = s.rstrip(string.digits + " ")
        return stripped[: cfg.anchor_len]
    return ""


def body_lines(lines: Sequence[str], cfg: Config = DEFAULT_CONFIG) -> Sequence[str]:
    """文章页取正文：跳过顶部那条「新消息横幅」。

    很多应用在阅读文章时会在顶部浮一条消息通知（「某某: 在吗」）。
    它会被 OCR 抓到正文前面，拼进去就成了「文章里夹着聊天」。
    做法：在前几行里找第一行足够长的（≥ body_min_chars），从那行开始算正文。
    找不到足够长的行时，退一步只剥掉那些「明显是横幅」的行（短行 + 聊天特征）。
    """
    head = lines[: cfg.body_scan_lines]
    pats = cfg.compiled()
    for i, line in enumerate(head):
        s = line.strip()
        if len(s) < cfg.body_min_chars:
            continue
        # 控件行（+关注 / 写留言 / 点赞…）不是正文，别拿它当正文起点
        if pats.article and pats.article.search(s):
            continue
        return lines[i:]
    # 全屏都是短行：剥掉确实像「通知横幅」的那些（2~8 字、非控件行），其余保留。
    # 阈值故意卡在 8 字：真实文章正文行一般 15~30 字，不会这么短；
    # 而横幅就是「张三」「在吗」这种 2~3 个字。
    cut = 0
    for i, line in enumerate(head):
        s = line.strip()
        is_banner_like = (
            len(s) <= cfg.body_banner_max_chars
            and not (pats.article and pats.article.search(s))
        )
        if is_banner_like:
            cut = i + 1
            continue
        break
    return lines[cut:] if cut else lines


def chat_anchor(lines: Sequence[str], cfg: Config = DEFAULT_CONFIG,
                pats: CompiledPatterns | None = None) -> str:
    """聊天页的「同一会话」判据。

    不能只看第一行：聊天页滚动时，第一行是**第一条消息**会变，页头（联系人名）
    可能被滚出屏幕。实测里两种页面都存在，所以做一个鲁棒判据：

      1. 若第一行不是「发言人: 内容」形态 → 它就是页头，直接用（最常见）
      2. 否则 → 用本屏出现过的发言人集合（排序后拼接），同一会话的发言人集合稳定

    第 2 种在「页头滚出屏幕」时特别有用：不同会话的发言人集合几乎不会重合。
    """
    p = pats or cfg.compiled()
    for line in lines[:2]:
        s = line.strip()
        if not s or p.status.match(s):
            continue
        if not p.chat.match(s):
            return s.rstrip(string.digits + " ")[: cfg.anchor_len]
        break

    speakers: list[str] = []
    for line in lines:
        m = p.chat.match(line)
        if not m:
            continue
        name = line.split(":", 1)[0].split("：", 1)[0].strip()
        if name and name not in speakers:
            speakers.append(name)
    return "|".join(sorted(speakers)[:4])[: cfg.anchor_len * 2]



def normalize(text: str, cfg: Config = DEFAULT_CONFIG) -> str:
    """整段归一化，用于判「内容一个字都没变」。"""
    if not cfg.collapse_ws:
        return text
    return " ".join(text.split())


def clean_lines(raw: str, min_len: int = 1) -> list[str]:
    """把 OCR 出来的整段文本切成「有意义」的行：去空行、去纯符号、去重后再返回。

    注意：这里**不做跨屏去重**，跨屏去重是 Accumulator 的活——
    同一屏里重复出现的行（如列表里的分隔符）保留原位更利于比对。
    """
    out: list[str] = []
    for line in raw.splitlines():
        s = line.strip()
        if len(s) < min_len:
            continue
        if all(not ch.isalnum() for ch in s):   # 纯标点/纯符号行
            continue
        out.append(s)
    return out
