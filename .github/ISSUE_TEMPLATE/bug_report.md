---
name: Bug report
about: Something merged that shouldn't have, or split that shouldn't have
title: "[bug] "
labels: bug
---

## What went wrong

<!-- Pick one, it makes triage much faster -->
- [ ] Two unrelated pages got merged into one record
- [ ] One page got split into several records
- [ ] A page type was misclassified
- [ ] Crash / exception
- [ ] Other

## The two frames

**Redact all real content.** Replace names with `Alice` / `Bob` and messages with
`Message text`. This gets published permanently, so treat it like a public paste.

Frame A (previous):
```json
{"ts": 1000.0, "lines": ["...", "..."]}
```

Frame B (current):
```json
{"ts": 1030.0, "lines": ["...", "..."]}
```

## What you expected

<!-- e.g. "these are two different conversations, should be two records" -->

## What actually happened

<!-- Include gate_log if you have it — it names the gate that let it through -->

```json
{"time_window": true, "same_type": true, "same_anchor": true,
 "anchor_relaxed": false, "overlap_enough": true}
```

## Config you're using

<!-- Only if you changed the defaults -->
```python
Config(window_s=..., max_lines=..., min_overlap=...)
```

## Environment

- ScrollBreaker version:
- Python:
- OS:
- OCR engine:
