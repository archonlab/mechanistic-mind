from __future__ import annotations

from mechanistic_mind.ui.psychology_observer.model import PsychologyTelemetryProjector


def test_projector_surfaces_depth_and_autonomous_fields() -> None:
    projector = PsychologyTelemetryProjector()
    projector.apply(
        {
            "record_type": "run_metadata",
            "payload": {
                "run_id": "t",
                "engine_version": "0.5.3",
                "seed": 1,
                "world_type": "ContextualObjectEcologyWorld",
                "mechanism_versions": {"PSYCHE-SINGLE-ORGANISM-V05": "0.5.3"},
                "config": {
                    "autonomous_dynamics_enabled": True,
                    "world_dynamics": "dynamic",
                },
            },
        }
    )
    projector.apply(
        {
            "record_type": "tick",
            "payload": {
                "tick": 0,
                "observations": {
                    "A001": {
                        "data": {
                            "position": [1, 1],
                            "visible_objects": [],
                        }
                    }
                },
                "actions": {"A001": {"kind": "WAIT", "params": {}}},
                "action_sources": {
                    "A001": "MECHANISM:PSYCHE-SINGLE-ORGANISM-V05"
                },
                "signals": {},
                "state_after": {
                    "world": {
                        "variables": {
                            "world": {
                                "width": 8,
                                "height": 8,
                                "objects": {
                                    "OBJ_A": {
                                        "position": [2, 2],
                                        "autonomous": {"enabled": True},
                                    }
                                },
                                "obstacles": {},
                                "agent_positions": {"A001": [1, 1]},
                            },
                            "autonomous_events": [
                                {
                                    "kind": "AUTONOMOUS_OBJECT_MOVED",
                                    "object_id": "OBJ_A",
                                }
                            ],
                            "causal_provenance_tick": {
                                "tick": 0,
                                "enabled": True,
                                "events": [
                                    {
                                        "kind": "AUTONOMOUS_OBJECT_MOVED",
                                        "object_id": "OBJ_A",
                                    }
                                ],
                                "categories": ["AUTONOMOUS_MOTION"],
                            },
                            "developmental_history": [
                                {
                                    "world_action_receipt": {
                                        "autonomous_update_kinds": [
                                            "AUTONOMOUS_OBJECT_MOVED"
                                        ],
                                        "causal_provenance_tick": {
                                            "enabled": True,
                                            "events": [
                                                {
                                                    "kind": "AUTONOMOUS_OBJECT_MOVED",
                                                    "object_id": "OBJ_A",
                                                }
                                            ],
                                        },
                                    }
                                }
                            ],
                        }
                    },
                    "agents": {
                        "A001": {
                            "mechanism_states": {
                                "PSYCHE-SINGLE-ORGANISM-V05": {
                                    "psyche": {
                                        "memory": {
                                            "developmental": {
                                                "condition": "EXPERIENCE_GATED",
                                                "cognitive_depth": 1.2,
                                                "local_experience_maturity": 0.4,
                                                "developmental_maturity": 0.5,
                                                "depth_limitation_reason": "local",
                                                "developmental_stage": "CHILD",
                                                "gate_factor": 0.4,
                                            }
                                        },
                                        "working": {
                                            "sensorimotor_generation": {
                                                "history_used": 2,
                                                "candidates_after_gate": 3,
                                            }
                                        },
                                    }
                                }
                            }
                        }
                    },
                },
                "mechanism_outputs": {"A001": {}},
            },
        }
    )
    tick = projector.view.latest
    assert tick is not None
    assert tick.cognitive_depth == 1.2
    assert tick.local_experience_maturity == 0.4
    assert tick.developmental_stage == "CHILD"
    assert tick.world_dynamics_enabled is True
    assert tick.passive_change is True
    assert "AUTONOMOUS_OBJECT_MOVED" in tick.autonomous_update_kinds
