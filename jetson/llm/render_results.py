#!/usr/bin/env python3
"""Render every results/*.json into a readable results/*.md (one section per prompt:
question, answer, tool calls, reasoning text, timing, score). Standard library only.

Usage: python3 jetson/llm/render_results.py
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def render(path):
    r = json.load(open(path))
    out = [f"# {r['label']}", "",
           f"Run {r['started']} → {r['finished']} · server model `{r['server_props'].get('model_path')}` · "
           f"n_ctx {r['server_props'].get('n_ctx')} · max_tokens {r['max_tokens']} · prompts {r['prompts_version']}", ""]
    agg = r.get("aggregate", {})
    out.append("## Summary")
    out.append("")
    out.append("| Section | Pass | Fail | Review | n |")
    out.append("|---|---|---|---|---|")
    for k, v in agg.get("sections", {}).items():
        out.append(f"| {k} | {v['pass']} | {v['fail']} | {v['review']} | {v['n']} |")
    out.append("")
    out.append(f"Generation median {agg.get('gen_tok_s_median') and round(agg['gen_tok_s_median'], 1)} tok/s · "
               f"prompt median {agg.get('prompt_ms_median') and round(agg['prompt_ms_median'])} ms")
    out.append("")
    section = None
    for it in r["items"]:
        if it["section"] != section:
            section = it["section"]
            out += [f"## {section}", ""]
        verdict = "PASS" if it["pass"] else ("FAIL" if it["pass"] is False else "review")
        out.append(f"### {it['id']} — {verdict} ({it['why']})")
        out.append("")
        out.append(f"**Prompt:** {it['prompt']}")
        out.append("")
        if it.get("expect"):
            out.append(f"**Expected:** `{json.dumps(it['expect'], ensure_ascii=False)}`")
            out.append("")
        if it.get("error"):
            out.append(f"**Error:** {it['error']}")
            out.append("")
        if it.get("tool_calls"):
            calls = "; ".join(f"`{c['name']}({c['arguments']})`" for c in it["tool_calls"])
            out.append(f"**Tool calls:** {calls}")
            out.append("")
        content = (it.get("content") or "").strip()
        out.append("**Answer:** " + (content if content else "_(empty)_"))
        out.append("")
        reasoning = (it.get("reasoning") or "").strip()
        if reasoning:
            out.append("<details><summary>Reasoning (" + str(len(reasoning)) + " chars)</summary>")
            out.append("")
            out.append(reasoning)
            out.append("")
            out.append("</details>")
            out.append("")
        t = []
        if it.get("prompt_tokens") is not None:
            t.append(f"prompt {it['prompt_tokens']} tok in {it.get('prompt_ms') and round(it['prompt_ms'])} ms")
        if it.get("completion_tokens") is not None:
            t.append(f"generated {it['completion_tokens']} tok in {it.get('predicted_ms') and round(it['predicted_ms'])} ms")
        if it.get("gen_tok_s"):
            t.append(f"{round(it['gen_tok_s'], 1)} tok/s")
        if it.get("wall_s") is not None:
            t.append(f"wall {it['wall_s']} s")
        if t:
            out.append("_" + " · ".join(t) + "_")
            out.append("")
    md = path[:-5] + ".md"
    with open(md, "w") as f:
        f.write("\n".join(out))
    return md


if __name__ == "__main__":
    for p in sorted(glob.glob(os.path.join(HERE, "results", "*.json"))):
        print("wrote", render(p))
