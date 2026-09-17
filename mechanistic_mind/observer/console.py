from __future__ import annotations

from .models import RunMetadata, RunSummary, TickRecord


class ConsoleSink:
    """Compact live observer for a standalone terminal session."""

    def __init__(self, *, show_signals: bool = True) -> None:
        self.show_signals = show_signals

    def write_run_metadata(self, metadata: RunMetadata) -> None:
        print(
            f"[Observer] run={metadata.run_id} "
            f"seed={metadata.seed} world={metadata.world_type}"
        )
        print(
            "[Observer] mechanisms="
            + ", ".join(
                f"{mid}@{version}"
                for mid, version in metadata.mechanism_versions.items()
            )
        )

    def write_tick(self, record: TickRecord) -> None:
        for agent_id in sorted(record.actions):
            action = record.actions[agent_id]["kind"]
            source = record.action_sources.get(agent_id, "UNKNOWN")
            observation = record.observations.get(agent_id, {}).get("data", {})
            consequence = observation.get(
                "last_experienced_effects",
                observation.get(
                    "last_consequence",
                    observation.get("last_outcome"),
                ),
            )

            message = (
                f"[t={record.tick:04d}] {agent_id} "
                f"action={action} source={source} "
                f"last_experience={consequence}"
            )
            if self.show_signals:
                message += f" signals={record.signals.get(agent_id, {})}"
            print(message)

    def write_run_summary(self, summary: RunSummary) -> None:
        print(
            f"[Observer] completed run={summary.run_id} "
            f"ticks={summary.ticks_recorded} final_tick={summary.final_tick}"
        )
