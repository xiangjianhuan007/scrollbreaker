# Contributing to ScrollBreaker

Thanks for looking. This project has a **very narrow scope on purpose** — read this
before opening a PR, because the most common PR will be rejected for being out of scope,
not for being bad code.

## What this project is

A library that decides **whether two consecutive screen captures are the same page**.
That is the whole job.

## What this project will never accept

These are not "we haven't gotten to it yet" — they are hard no:

- **Reading application databases**, decrypting local storage, or extracting keys.
  The moment this project does that, it can no longer be used safely by anyone.
- **Process injection, hooking, accessibility-API scraping of another app's internals.**
  Same reason.
- **Authentication bypass** of any kind.
- **Bundled OCR models or API keys.** OCR stays a plug-in you supply.
- **Telemetry, analytics, "anonymous usage stats".** No network calls, period.

If you need those things, fork it — but don't send them here.

## What we want

- **New page-type detectors.** Different apps signal "this is an article" differently.
  If you have patterns for a real app, that's a genuinely useful contribution.
- **Better anchor heuristics.** The chat-speaker-set fallback works; something better
  probably exists.
- **Regression cases.** This is the highest-value contribution. If ScrollBreaker merged
  two things that should not have been merged, send the two frames (with content
  replaced by dummy text) and we will add them to the test suite.
- **OCR adapters** for engines you actually use.
- **Docs fixes**, especially if a paragraph made you misunderstand the design.

## Before you open a PR

```bash
pip install -e ".[dev]"
pytest -q          # must be green
```

Then answer these three in the PR description:

1. **Which gate does this affect?** (time / type / anchor / overlap / none)
2. **What real scenario broke without this change?** Describe the frames.
3. **Does it make `test_article_to_chat_never_merged` still pass?** It must.

## Ground rules for the merge logic

The accumulator is the core. Changes there need to respect one invariant:

> **When in doubt, break the record.** A wrongly-split record is a minor
> inconvenience — you get two entries instead of one. A wrongly-merged record is
> silent data corruption that surfaces weeks later as a model that "hallucinates"
> things nobody said.

Bias toward splitting, always.

## Real content in issues and PRs

Do not paste real chat logs, real names, real screenshots, or screenshots of messages.
Redact to `Alice` / `Bob` / `Message text`. Issues with real personal content will be
edited or closed — not because we don't care, but because it would be republished
forever in the issue tracker.

## Commit style

Conventional-ish, one line, imperative mood:

```
fix: relax anchor check for article pages
feat: add list-page detector patterns for feed apps
test: add regression case for banner-stripped article scroll
docs: clarify why overlap alone is not enough
```

## License

By contributing you agree your work is released under the MIT license in `LICENSE`.
