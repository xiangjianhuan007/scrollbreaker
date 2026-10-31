# Security Policy

## Scope

ScrollBreaker reads pixels and text. It has no network code, no credential handling,
and no write access outside the output file you name.

## What is in scope for a report

- A code path that sends captured content off the machine
- A path that reads files other than the frames you pass in
- Arbitrary code execution via OCR command construction (`CmdOCR`)
- Denial of service via crafted frames (unbounded memory / CPU)

## What is out of scope

- **The fact that it captures screen content at all.** That is the feature. If you
  run it while sensitive content is on screen, that content will be captured — audit
  your own `Config` and capture region.
- **The compliance posture of your use case.** Whether you may legally capture a given
  screen is a question for you and your counsel, not a vulnerability.
- Reports that require the attacker to already have code execution on the machine.

## Reporting

Open a private security advisory on this repository
(Security → Advisories → New draft advisory). Do not open a public issue.

Please include: affected version, minimal reproduction, and what an attacker gains.

## Known limitations, stated plainly

- `CmdOCR` builds a command line from a user-supplied argv. It substitutes `{img}`
  with a temp path and does not shell-interpret, but it will happily run whatever
  executable you pass. **Do not feed it untrusted input.**
- The output JSONL is plain text, unencrypted, with no access control beyond the
  filesystem. If you capture sensitive content, secure the file yourself.
