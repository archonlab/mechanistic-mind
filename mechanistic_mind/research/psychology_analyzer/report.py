from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping


def esc(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return html.escape(str(value))


def table(headers: list[str], rows: list[list[Any]]) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def write_html_report(path: Path, summary: Mapping[str, Any], events: list[Mapping[str, Any]], epochs: list[Mapping[str, Any]], biography: Mapping[str, Any]) -> None:
    dynamics = summary.get("dynamics", {})
    cards = [
        ("Ticks", dynamics.get("ticks_analyzed")),
        ("Meaningful events", len(events)),
        ("Behavioral epochs", len(epochs)),
        ("Invalid JSON", summary.get("invalid_json_lines")),
    ]
    cards_html = "".join(f"<div class='card'><span>{esc(label)}</span><strong>{esc(value)}</strong></div>" for label, value in cards)
    biography_html = "".join(
        "<article class='bio'><p>" + esc(paragraph.get("text")) + "</p>"
        + "<details><summary>Show evidence</summary><pre>" + esc({
            "claims": paragraph.get("claims"),
            "evidence_ticks": paragraph.get("evidence_ticks"),
            "source_lines": paragraph.get("source_lines"),
        }) + "</pre></details></article>"
        for paragraph in biography.get("paragraphs", [])
    )
    epoch_rows = [[
        epoch.get("epoch_id"), f"{epoch.get('start_tick')}–{epoch.get('end_tick')}", epoch.get("label"),
        epoch.get("dominant_action"), epoch.get("dominant_object"), epoch.get("samples"),
        epoch.get("mean_selected_uncertainty"), epoch.get("mean_absolute_prediction_error"),
    ] for epoch in epochs]
    event_html = "".join(
        f"<details class='event'><summary><span class='tick'>t{esc(event.get('tick'))}</span> {esc(event.get('type'))} <small>confidence {esc(event.get('confidence'))}</small></summary>"
        f"<pre>{esc({'evidence': event.get('evidence'), 'provenance': event.get('provenance')})}</pre></details>"
        for event in events
    )
    action_rows = [[key, value] for key, value in dynamics.get("action_counts", {}).items()]
    object_rows = [[key, value] for key, value in dynamics.get("object_interaction_counts", {}).items()]
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Psychology Analyzer v0.2</title>
<style>
:root{{--bg:#0b1018;--panel:#121a26;--panel2:#182334;--text:#edf2f7;--muted:#9eb0c4;--line:#29384c;--accent:#76d7c4;--accent2:#8eb7ff}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 10% 0,#173047 0,transparent 34%),var(--bg);color:var(--text);font:15px/1.55 system-ui,sans-serif}}
main{{max-width:1280px;margin:auto;padding:42px 24px 80px}} h1{{font-size:clamp(32px,5vw,58px);margin:0 0 8px;letter-spacing:-.04em}} h2{{margin-top:0;font-size:24px}} .eyebrow{{color:var(--accent);font-weight:700;text-transform:uppercase;letter-spacing:.12em}} .note{{color:var(--muted);max-width:850px}} .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:28px 0}} .card,section{{background:linear-gradient(145deg,var(--panel2),var(--panel));border:1px solid var(--line);border-radius:16px;box-shadow:0 12px 34px #0004}} .card{{padding:18px}} .card span{{display:block;color:var(--muted)}} .card strong{{font-size:30px}} section{{padding:24px;margin:18px 0}} .bio{{border-left:3px solid var(--accent);padding:2px 0 2px 18px;margin:20px 0}} details{{border-top:1px solid var(--line);padding:10px 0}} summary{{cursor:pointer;color:var(--accent2);font-weight:650}} pre{{white-space:pre-wrap;word-break:break-word;background:#080d14;padding:12px;border-radius:9px;color:#cfe0f4}} table{{width:100%;border-collapse:collapse}} th,td{{padding:10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}} th{{color:var(--accent2)}} .table-wrap{{overflow:auto}} .event small{{color:var(--muted);font-weight:400}} .tick{{display:inline-block;min-width:68px;color:var(--accent)}}
</style></head><body><main>
<div class="eyebrow">Mechanistic Mind · evidence-derived</div><h1>Psychology Analyzer v0.2</h1>
<p class="note">{esc((summary.get('interpretation_boundary') or {}).get('statement'))}</p>
<div class="cards">{cards_html}</div>
<section><h2>{esc(biography.get('title'))}</h2>{biography_html or '<p class="note">No biography claims could be supported.</p>'}</section>
<section><h2>Behavioral epochs</h2>{table(['Epoch','Ticks','Evidence-derived label','Dominant action','Dominant object','Samples','Mean uncertainty','Mean |error|'], epoch_rows)}</section>
<section><h2>Meaningful events</h2><p class="note">Nested model internals are summarized as direct associations; they are not recursively expanded.</p>{event_html or '<p class="note">No meaningful changes crossed the conservative evidence rules.</p>'}</section>
<section><h2>Action dynamics</h2>{table(['Action','Count'], action_rows)}</section>
<section><h2>Object interactions</h2>{table(['Object','Count'], object_rows)}</section>
<section><h2>Body-state ranges</h2>{table(['Variable','Range'], [[key,value] for key,value in dynamics.get('body_ranges',{}).items()])}</section>
<section><h2>Run provenance</h2><pre>{esc({'source':summary.get('source'),'metadata':summary.get('metadata'),'timeline_kept':summary.get('timeline_kept'),'ignored_records':summary.get('ignored_records')})}</pre></section>
</main></body></html>"""
    path.write_text(document, encoding="utf-8")
