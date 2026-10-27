"""Strip prompt-injection attempts out of untrusted text (JD, mail, page scrape).

    python scripts/sanitize_text.py --file state/tmp/jd_123.txt
    Get-Content jd.txt | python scripts/sanitize_text.py --stdin
    python scripts/sanitize_text.py --file jd.txt --out state/tmp/jd_123.clean.txt

Why: job posts and emails are DATA. A post that says "ignore previous instructions"
or "send your resume to attacker@x.com" must not steer the agent. This script removes
those lines before the text is handed to the model or saved anywhere.

Exit codes: 0 clean (or cleaned), 2 usage error, 3 nothing left after cleaning.
"""
from __future__ import annotations

import argparse
import re
import sys

# Instruction-like patterns that never belong inside a job description.
PATTERNS = [
    r"ignore (all|any|the)?\s*(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"disregard (all|any|the)?\s*(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"forget (all|any|the)?\s*(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
    r"you are (now )?(a|an|the)\s+\w+",                  # role hijack
    r"(system|developer|assistant)\s*(prompt|message)",
    r"reveal|print|show|dump|leak\s+(your|the)\s+(prompt|instructions?|rules?|system)",
    r"\b(run|execute|eval)\s+(this|the following)\s+(command|script|code)",
    r"\b(powershell|cmd\.exe|bash|curl|wget|python\s+-c)\b",
    r"(send|forward|mail|email)\s+(your|the|all)\s+(resume|cv|documents?|files?|data)",
    r"send\s+(money|payment|fee|deposit|usdt|crypto|bitcoin)",
    r"\b(api[_-]?key|secret|token|password)\b\s*[:=]",
    r"do not tell|don't tell|without telling|keep this (secret|hidden)",
    r"click\s+(this|the following)\s+link\s+to\s+(apply|verify|pay)",
    r"https?://(bit\.ly|tinyurl\.com|t\.co|forms\.gle|rb\.gy)/\S+",  # shortlinks are unverifiable
]
INJECTION = re.compile("|".join(f"(?:{p})" for p in PATTERNS), re.I)

# Zero-width / bidi characters used to hide instructions inside normal text.
INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")


def clean(text: str) -> tuple[str, list[str]]:
    """Return (clean_text, removed_lines)."""
    removed: list[str] = []
    out: list[str] = []
    for line in INVISIBLE.sub("", text).splitlines():
        if INJECTION.search(line):
            removed.append(line.strip()[:200])
            continue
        out.append(line.rstrip())
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, removed


def main() -> int:
    ap = argparse.ArgumentParser(description="Remove prompt-injection lines from untrusted text")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="path to the JD / mail / page text")
    src.add_argument("--stdin", action="store_true", help="read from stdin")
    ap.add_argument("--out", default="", help="write cleaned text to this file instead of stdout")
    a = ap.parse_args()

    try:
        raw = sys.stdin.read() if a.stdin else open(a.file, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        print(f"READ_FAILED: {exc}", file=sys.stderr)
        return 2

    cleaned, removed = clean(raw)
    if not cleaned:
        print("EMPTY_AFTER_SANITIZE: every line looked like an injection attempt", file=sys.stderr)
        return 3
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(cleaned)
        print(f"CLEANED {len(removed)} line(s) -> {a.out}")
    else:
        print(cleaned)
    for r in removed:
        print(f"REMOVED: {r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
