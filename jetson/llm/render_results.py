#!/usr/bin/env python3
"""Turn results/*.json into tables.

  results/<run>.md         one row per prompt: question | answer or tool call | score | tok/s | seconds
  results/comparison.md    the same prompts with every complete run's answer side by side, plus a metrics table

Standard library only. Usage: python3 jetson/llm/render_results.py
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")


def cell(text, limit=None):
    text = (text or "").replace("|", "\\|").replace("\n", " ").strip()
    if limit and len(text) > limit:
        text = text[:limit] + "…"
    return text or "_(empty)_"


def answer_of(it):
    if it.get("error"):
        return "ERROR: " + it["error"]
    if it.get("tool_calls"):
        return "; ".join(f"`{c['name']}({c['arguments']})`" for c in it["tool_calls"]) + (
            " + " + it["content"].strip() if (it.get("content") or "").strip() else "")
    return it.get("content") or ""


def verdict(it):
    return "PASS" if it["pass"] else ("FAIL" if it["pass"] is False else "")


def load_runs():
    runs = []
    for p in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        r = json.load(open(p))
        r["_file"] = os.path.basename(p)
        r["_complete"] = not any(i.get("error") for i in r["items"])
        runs.append(r)
    return runs


def run_table(r):
    out = [f"# {r['label']}", "",
           f"{r['started']} to {r['finished']} · n_ctx {r['server_props'].get('n_ctx')} · max_tokens {r['max_tokens']} · prompts {r['prompts_version']}",
           "", "| # | Section | Question | Answer | Score | tok/s | s |", "|---|---|---|---|---|---|---|"]
    for it in r["items"]:
        g = it.get("gen_tok_s")
        out.append(f"| {it['id']} | {it['section']} | {cell(it['prompt'], 160)} | {cell(answer_of(it))} | {verdict(it)} {cell(it['why']) if it['pass'] is False else ''} | {round(g, 1) if g else ''} | {it.get('wall_s') if it.get('wall_s') is not None else ''} |")
    agg = r.get("aggregate", {})
    out += ["", "| Section | Pass | Fail | Review | n |", "|---|---|---|---|---|"]
    for k, v in agg.get("sections", {}).items():
        out.append(f"| {k} | {v['pass']} | {v['fail']} | {v['review']} | {v['n']} |")
    out.append("")
    out.append(f"Generation median {round(agg['gen_tok_s_median'], 1) if agg.get('gen_tok_s_median') else '-'} tok/s · prompt median {round(agg['prompt_ms_median']) if agg.get('prompt_ms_median') else '-'} ms")
    return "\n".join(out) + "\n"


def comparison(runs):
    runs = [r for r in runs if r["_complete"]]
    if not runs:
        return ""
    labels = [r["label"] for r in runs]
    out = ["# Side by side", "", "Complete runs only. Same prompts, same server flags, 4k context, max_tokens 400.", ""]
    out += ["| Metric | " + " | ".join(labels) + " |", "|---|" + "---|" * len(labels)]
    def agg(r, k):
        return r.get("aggregate", {}).get(k)
    out.append("| Generation tok/s (median) | " + " | ".join(str(round(agg(r, "gen_tok_s_median"), 1)) for r in runs) + " |")
    out.append("| Prompt ms (median) | " + " | ".join(str(round(agg(r, "prompt_ms_median"))) for r in runs) + " |")
    out.append("| Run time | " + " | ".join(f"{r['started'][11:16]}–{r['finished'][11:16]}" for r in runs) + " |")
    for sec in ["honesty", "tools", "no-tool", "hygiene", "context", "korean"]:
        vals = []
        for r in runs:
            v = r.get("aggregate", {}).get("sections", {}).get(sec)
            vals.append(f"{v['pass']}/{v['n']}" if v else "-")
        out.append(f"| {sec} pass | " + " | ".join(vals) + " |")
    out.append("")
    # prompts in the order of the first run
    ids = [it["id"] for it in runs[0]["items"]]
    by = [{it["id"]: it for it in r["items"]} for r in runs]
    out += ["| # | Question | " + " | ".join(labels) + " |", "|---|---|" + "---|" * len(labels)]
    for i in ids:
        q = next((b[i]["prompt"] for b in by if i in b), "")
        cells = []
        for b in by:
            it = b.get(i)
            if not it:
                cells.append("")
                continue
            v = verdict(it)
            cells.append((f"**{v}** " if v else "") + cell(answer_of(it)))
        out.append(f"| {i} | {cell(q, 140)} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    runs = load_runs()
    for r in runs:
        path = os.path.join(RESULTS, r["_file"][:-5] + ".md")
        with open(path, "w") as f:
            f.write(run_table(r))
        print("wrote", os.path.basename(path), "(complete)" if r["_complete"] else "(incomplete run)")
    with open(os.path.join(RESULTS, "comparison.md"), "w") as f:
        f.write(comparison(runs))
    print("wrote comparison.md")
