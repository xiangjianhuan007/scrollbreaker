# ScrollBreaker

**A scroll-aware screen content collector for LLM agents** — 一个会分辨页面的信息采集器。

> **Your LLM is eating garbage. The screenshots are the problem.**
>
> Every scroll-capture tool on the planet splices frames together by line overlap.
> That works — until it silently fuses an article and a chat log into one record
> that looks perfectly normal. ScrollBreaker stops that with **four gates**.

Most **information collectors** answer the question *"how do I grab the screen?"*
ScrollBreaker answers the harder one: *"are these two grabs the same page at all?"*


Screenshot → OCR → merge is the standard pipeline for feeding visual content to an
agent. It has one failure mode that poisons your dataset and never warns you:
**unrelated pages that happen to share lines.**

```
Article page : 正常 / 好的 / 收到 / 在看 / +关注 / body paragraph...
Chat page    : 正常 / 好的 / 收到 / Alice: stop machine 4 / Bob: on it
Shared lines : 3
```

Any tool that merges on "overlap ≥ 2" fuses these two. The result is one record
containing an article with a factory conversation stapled into its middle. It parses
fine. It embeds fine. It is **wrong**, and nothing downstream will tell you.

ScrollBreaker refuses to merge unless four gates all pass.

## The four gates

| # | Gate | Rule | Default |
|---|------|------|---------|
| 1 | Time window | Frames further apart than N seconds are a different reading session | `180s` |
| 2 | Same type | `article` / `chat` / `list` / `text` must match | — |
| 3 | Same anchor | Same page header (relaxed for articles — titles scroll away) | — |
| 4 | Real overlap | ≥ N **identical** lines, because 1 line is noise | `2` |

Fail any one → **new record, no merge. Ever.**

There is a fifth state, `mixed`: a frame containing both article and chat/list
signatures. That frame *is* a page transition in progress, so it can neither start
an accumulation nor be absorbed into one.

## Quick start

```bash
pip install -e .
# for live capture: pip install mss pillow
```

```python
from scrollbreaker import Accumulator, Frame, Mode

acc = Accumulator()                      # every threshold lives in Config

for snap in screenshots:                 # one frame every N seconds
    m = acc.push(Frame(lines=snap.lines, ts=snap.ts))

    if m.mode is Mode.ROLL:
        pass                             # same page scrolling; m.text is the full text
    else:
        handle_page(m.text)              # page changed; previous record is complete
```

Every decision is auditable — `m.gate_log` tells you which gate failed:

```python
{"time_window": True, "same_type": False, "same_anchor": False,
 "anchor_relaxed": True, "overlap_enough": False}
```

### CLI

```bash
# offline replay — tune thresholds without capturing anything
scrollbreaker replay examples/frames.jsonl

# live capture
scrollbreaker watch --interval 10 \
  --ocr-cmd tesseract {img} stdout -l eng --psm 6 \
  --output records.jsonl
```

Real output from `examples/frames.jsonl`:

```
frame 1  new   chat     anchor=Alice|Bob
frame 2  roll  chat     anchor=Alice|Bob   overlap=2       <- same conversation, merged
frame 3  new   article  same_type=false                    <- switched pages, hard break
```

That third line is the whole point: **wrong type, no merge — no matter the overlap.**

## Output shape

```json
{"ts": 1000.0, "mode": "roll", "page": "chat", "anchor": "Alice|Bob",
 "scene": "chat|Alice|Bob", "overlap": 2, "text": "..."}
```

`scene` is the field that matters downstream. Group by `scene` when you store,
embed, or summarize, and unrelated captures can no longer contaminate each other.

## Design trade-offs

**OCR is a plug-in.** The whole contract is `read(bytes) -> str`. Use tesseract,
PaddleOCR, a cloud API, a local VLM — ScrollBreaker never looks at pixels, only lines.

**Screen only, no database spelunking.** No file parsing, no process injection,
no root. You lose some fidelity versus reading the source directly; you gain
application-agnostic capture that survives app updates.

**Thresholds are empirical, not laws.** `180s / 80 lines / 2 overlap` came from real
long-form reading and group-chat scrolling. Monitoring a dashboard or a log tail?
Change `Config`.

**Chat anchors degrade gracefully.** A chat header scrolls out of view, at which point
the first line is a message, not a header. ScrollBreaker falls back to the set of
speakers seen in the frame — stable within a conversation, rarely shared across two.

## Test suite

```bash
pip install -e ".[dev]" && pytest -q
```

9 tests covering each gate. The one that matters is `test_article_to_chat_never_merged`:
two frames sharing **6 lines** with different page types must still produce two records.
It exists because that exact fusion happened and corrupted real data. Run it before
touching the merge logic.

## Compliance

- Reads **only what is visible on screen**. No application data files, no databases,
  no process memory.
- **No network, no telemetry.** Everything stays local; output is a JSONL on your disk.
- Capturing other people's screens, or redistributing captured content, may violate
  local law and the target platform's terms. **Use it on your own device, your own
  account, your own visible content.**
- This project provides no authentication bypass, no database decryption, and no
  process injection — and will not accept PRs that add them.

## 中文说明

**ScrollBreaker（破滚者）** —— 把滚动的屏幕切成能读的页。

核心不是「截图 + OCR」，是**判断两屏到底是不是同一页**。绝大多数采集工具按「有
两行重合」就拼，于是把一篇文章和一段聊天糊成一条记录——数据被污染了还看不出来。

四道闸门（时间窗 / 类型一致 / 页头一致 / 实质重合）全部通过才允许合并，任一条不过
就果断断开。`mixed`（一屏里同时出现文章和聊天特征）是切页中间态，既不累积也不被吸收。

阈值都在 `Config` 里，改成你的场景就行。

## License

MIT — do whatever you want, just don't blame us when your OCR is worse than ours.
