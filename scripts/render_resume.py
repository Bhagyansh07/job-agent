"""Render an ATS-friendly single-column PDF from a tailored JSON, with an anti-fabrication guard.

python scripts/render_resume.py --tailored state/tmp/tailored.json --out output/resumes/Company_Role.pdf
Guard: every skill and every number in the tailored resume must already exist in resume/master.json.

Design: reproduces Bhagyansh's own resume template 1:1 (measured forensically from his sample PDF).
US Letter, Liberation Serif / Times, centred header with a two-segment blue accent, centred name,
grey #444 full-width section rules under each heading, black italic right-aligned dates (pinned at
x=497.6), grey italic sub-lines. Single column, real text, so ATS parsing stays clean. HTML is
generated from the JSON and printed to PDF with headless Chrome.
"""
import argparse, json, re, sys, pathlib, subprocess
from xml.sax.saxutils import escape
from common import ROOT


def flat_skills(d):
    out = []
    for v in (d.get("skills") or {}).values():
        out += v if isinstance(v, list) else [v]
    return [s.strip() for s in out if s and s.strip()]


def guard(master, tailored):
    mtxt = json.dumps(master, ensure_ascii=False).lower()
    bad = []
    for s in flat_skills(tailored):
        if s.lower() not in mtxt:
            bad.append(f"skill not in master: {s}")
    ttxt = []
    for sec in ("experience", "projects"):
        for it in tailored.get(sec, []):
            ttxt += it.get("bullets", [])
    ttxt.append(tailored.get("summary", ""))
    for num in set(re.findall(r"\d[\d,.]*\+?%?", " ".join(ttxt))):
        if num.lower() not in mtxt:
            bad.append(f"number not in master: {num}")
    for sec in ("experience", "projects"):
        mnames = json.dumps(master.get(sec, []), ensure_ascii=False).lower()
        for it in tailored.get(sec, []):
            key = (it.get("company") or it.get("name") or "").lower()
            if key and key not in mnames:
                bad.append(f"{sec} item not in master: {key}")
    return bad


# Exact match to the sample: US Letter, serif, 10pt, grey #444 rules, blue #0563C1 accent,
# black italic dates pinned at x=497.6 (83.4pt in from the 581pt right rule edge).
CSS = """
@page { size: 612pt 792pt; margin: 18pt 31pt 24pt 31pt; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Liberation Serif","Times New Roman",Times,serif; font-size:10pt;
       line-height:1.15; color:#000; }
.header { text-align:center; padding-bottom:2pt; }
.name { font-size:16pt; font-weight:bold; text-transform:uppercase; line-height:1.1;
        letter-spacing:0.2pt; color:#000; }
.contact { font-size:9pt; line-height:1.15; color:#000; margin-top:2pt; }
.contact a { color:#0563C1; text-decoration:none; }
.contact .sep { margin:0 3pt; color:#000; }
.accent { display:flex; justify-content:center; align-items:center; gap:6.4pt;
          margin-top:2pt; margin-bottom:0; }
.accent i { display:block; width:128pt; height:0.5pt; background:#0563C1; }
.sec-head { font-size:10pt; font-weight:bold; text-transform:uppercase; color:#1F1F1F;
            border-bottom:0.75pt solid #444; padding-bottom:1.5pt; line-height:1.15;
            margin-top:6pt; }
.sec-body { margin-top:2.5pt; }
.para { font-size:10pt; line-height:1.15; }
.trow { display:flex; justify-content:space-between; padding-right:83.4pt; line-height:1.21; }
.trow .title { font-size:10pt; font-weight:bold; color:#000; }
.trow .date { font-size:10pt; font-style:italic; color:#000; white-space:nowrap; }
.meta { font-size:10pt; font-style:italic; color:#444; line-height:1.21; margin-bottom:2pt; }
ul { list-style:none; margin:0; padding:0; }
li { font-size:10pt; color:#000; padding-left:13.5pt; text-indent:-9pt; line-height:1.15; }
.bm { white-space:pre; }
li + li { margin-top:1pt; }
"""


def _html(t):
    e = lambda x: escape(str(x or ""))
    P = []

    def sec(title):
        P.append(f'<div class="sec-head">{e(title)}</div><div class="sec-body">')

    def end():
        P.append("</div>")

    def trow(title, date):
        d = f'<span class="date">{e(date)}</span>' if date else ""
        P.append(f'<div class="trow"><span class="title">{e(title)}</span>{d}</div>')

    def meta(txt):
        P.append(f'<div class="meta">{e(txt)}</div>')

    def ul(items):
        if items:
            P.append("<ul>" + "".join(
                f'<li><span class="bm">\u2022\u0020\u0020</span>{e(i)}</li>' for i in items) + "</ul>")

    c = t.get("contact", {})
    parts = []
    for k in ("phone", "email", "linkedin", "location"):
        v = c.get(k)
        if not v:
            continue
        if k in ("email", "linkedin", "github", "portfolio"):
            href = ("mailto:" + v) if (k == "email" and "@" in v) else \
                   (v if v.startswith("http") else "https://" + v)
            parts.append(f'<a href="{e(href)}">{e(v)}</a>')
        else:
            parts.append(f"<span>{e(v)}</span>")
    contact = '<span class="sep">|</span>'.join(parts)
    header = (f'<div class="header"><div class="name">{e(t.get("name"))}</div>'
              f'<div class="contact">{contact}</div></div>')

    if t.get("summary"):
        sec("Career Objective")
        P.append(f'<div class="para">{e(t["summary"])}</div>')
        end()
    if t.get("education"):
        sec("Education")
        for x in t["education"]:
            trow(x.get("degree"), x.get("dates"))
            line = str(x.get("school") or "") + (f" | {x['score']}" if x.get("score") else "")
            meta(line)
        end()
    if t.get("skills"):
        sec("Relevant Skills")
        ul([f"{k}: {', '.join(v) if isinstance(v, list) else v}"
            for k, v in t["skills"].items()])
        end()
    if t.get("projects"):
        sec("Project Experience")
        for x in t["projects"]:
            trow(x.get("name"), x.get("dates"))
            if x.get("tech"):
                meta("Tech Stack: " + str(x.get("tech") or ""))
            ul(x.get("bullets", []))
        end()
    if t.get("certifications"):
        sec("Certifications")
        ul(t["certifications"])
        end()
    if t.get("experience"):
        sec("Leadership & Positions of Responsibility")
        for x in t["experience"]:
            trow(f"{x.get('title')} — {x.get('company')}", x.get("dates"))
            ul(x.get("bullets", []))
        end()
    if t.get("achievements"):
        sec("Additional Information")
        ul(t["achievements"])
        end()

    return ("<!DOCTYPE html><html><head><meta charset=\"utf-8\"><style>" + CSS +
            "</style></head><body>" + header + "".join(P) + "</body></html>")


def _find_chrome():
    import os
    cands = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return None


def render(t, out):
    tmp = ROOT / "state" / "tmp" / "_resume.html"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(_html(t), encoding="utf-8")
    out = pathlib.Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    chrome = _find_chrome()
    if not chrome:
        raise RuntimeError("No Chrome/Edge found for HTML->PDF")
    import tempfile, shutil
    udd = tempfile.mkdtemp(prefix="chrome_pdf_")
    try:
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={udd}", "--no-pdf-header-footer",
             f"--print-to-pdf={out}", tmp.as_uri()],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
    finally:
        shutil.rmtree(udd, ignore_errors=True)
    if not out.exists():
        raise RuntimeError("Chrome did not produce the PDF")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tailored", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--master", default=str(ROOT / "resume" / "master.json"))
    a = ap.parse_args()
    master = json.loads(pathlib.Path(a.master).read_text(encoding="utf-8"))
    tailored = json.loads(pathlib.Path(a.tailored).read_text(encoding="utf-8"))
    bad = guard(master, tailored)
    if bad:
        print("FABRICATION_GUARD_FAILED:\n" + "\n".join(bad))
        sys.exit(2)
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    render(tailored, out)
    print(f"OK {out}")
