# NN · Chapter title

**Goal:** one sentence — what the reader can do/explain after this chapter.
**Prerequisites:** previous chapters / tools. **Time:** estimate.

> Optional one-paragraph framing: the problem this phase solves, in everyday language.

---

## N.1 Concept first (why before how)
- Plain-English explanation + a real-world analogy.
- A diagram (Mermaid `flowchart` / `sequenceDiagram`, or ASCII). Every major idea gets one.
- A comparison table when there are alternatives (and why we chose ours).

> 💡 **Learning Thought** — the durable insight, not the mechanics.

## N.2 Walk through the code
- Link to the real files (relative links). Show short, **exact** excerpts.
- Explain *why* each piece exists, not just what it does.

▶ **Try it** — runnable commands with the **real, captured** output pasted below. Never invent output.

> ⚠️ **Trap** — a mistake someone actually made, with the real error message and the fix.

## N.3 What went wrong while building it (if anything)
Bugs found, surprises, dead ends. These are the most valuable parts for a newcomer. Add them to `troubleshooting.md` too.

## 🧪 Labs
Small exercises that use the real repo. Solutions inside `<details>`.

## 🎯 Interview Questions
3–6 questions with model answers (these double as code-review prompts).

## ✅ Self-check
Tick-box list. If the reader can't tick it, they re-read.

## 📚 Further reading
External links — **curl-check every URL** before committing.

**Next:** link to the next chapter.

---
### Author checklist (delete before publishing)
- [ ] Every ▶ block was executed; outputs are real (trim, don't invent).
- [ ] Every code excerpt matches the repo (re-run extracted snippets, or link the file).
- [ ] New terms are in `glossary.md`; new commands in `cheatsheet.md`; new errors in `troubleshooting.md`.
- [ ] Rule IDs referenced exist in `docs/architecture/STANDARDS.md`.
- [ ] Links checked; `00-INDEX.md` table updated.
- [ ] A reader who skipped the previous chapter can still follow (link, don't assume).
