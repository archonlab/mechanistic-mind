# ANALYZER_SAVED_RUN_LIST_PAYLOAD_AND_EXPORT_CONTROLS_REPAIR_V1

## Root cause

`TickStory.derived_changes` is a **list** of kinded records. Volumetric
`_body_xyz_from_story` called `.get("pose")` on that list →
`AttributeError: 'list' object has no attribute 'get'` during saved-run (and
current-run) heavy analysis once POSE_STATE joins populated the list.

## Repair

1. Central pose/derived_changes normalization in volumetric reconstruction.
2. Evidence payload normalizer for list/dict/JSONL envelopes.
3. Analyzer FAILED exposes `error_code` + `failed_phase`.
4. UI: IDLE/RUNNING/COMPLETE/FAILED; clear source identity; no hybrid waiting.
5. Export from structured completed result: COPY REPORT / SAVE .MD / SAVE .JSON.

## Evidence

`results/analyzer_saved_run_list_payload_and_export_controls_repair_v1/`

## Next

Resume existing roadmap. Do not begin FIRST_HABITABLE in this task.
