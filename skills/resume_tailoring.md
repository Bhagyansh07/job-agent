# Resume tailoring (ATS-first, truthful)
Input: JD text + resume/master.json. Output: state/tmp/tailored.json -> PDF via render_resume.py.
Steps:
1. Extract from JD: job title, top 8-12 keywords (tech + skills), must-have vs nice-to-have.
2. Copy master.json to state/tmp/tailored.json and edit:
   - summary: 2 lines (this is the only headline the template renders), uses JD's exact keywords that he really has.
   - skills: reorder so JD-matching skills come first; use the JD's spelling for the SAME skill (e.g. "Node.js" vs "NodeJS", "REST APIs"). Remove irrelevant skills if the list is long. NEVER add a skill that is not in master.json.
   - projects/experience: reorder by relevance, re-word bullets to put JD keywords + his real impact first. Keep every number exactly as in master. Do not invent metrics.
   - keep to 1 page. Plain text, single column, standard headings (Summary, Skills, Experience, Projects, Education).
3. `python scripts/render_resume.py --tailored state/tmp/tailored.json --out "output/resumes/<Company>_<Role>.pdf"`
   - exit code 2 (FABRICATION_GUARD_FAILED) => fix the JSON (remove the flagged skill/number) and run again. The guard has no bypass.
4. Upload this PDF in the application. Record the filename in the tracker.
Note: no resume can "guarantee" ATS selection. Maximise: exact keyword match, clean format, relevant projects first.
