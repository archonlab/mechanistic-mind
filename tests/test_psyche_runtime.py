from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.psyche import (
    PsycheActionCandidate,
    PsycheContractError,
    PsycheContext,
    PsycheModule,
    PsycheOutput,
    PsycheRuntime,
    PsycheSelection,
    PsycheStage,
    PsycheState,
    PsycheUpdate,
)


class WriterA(PsycheModule):
    module_id = "A"
    stage = PsycheStage.PERCEPTION

    def process(self, context: PsycheContext) -> PsycheOutput:
        return PsycheOutput(
            updates=(PsycheUpdate("working", "x", 1),)
        )


class WriterB(PsycheModule):
    module_id = "B"
    stage = PsycheStage.PERCEPTION

    def process(self, context: PsycheContext) -> PsycheOutput:
        return PsycheOutput(
            updates=(PsycheUpdate("working", "x", 2),)
        )


class LaterReader(PsycheModule):
    module_id = "C"
    stage = PsycheStage.ATTENTION

    def process(self, context: PsycheContext) -> PsycheOutput:
        value = int(context.state.working.get("x", 0))
        return PsycheOutput(
            updates=(PsycheUpdate("working", "seen", value),)
        )


class CandidateMaker(PsycheModule):
    module_id = "MAKE"
    stage = PsycheStage.ACTION_GENERATION

    def process(self, context: PsycheContext) -> PsycheOutput:
        return PsycheOutput(
            candidates=(
                PsycheActionCandidate(
                    source_module=self.module_id,
                    action=Action("GO"),
                    total_value=1.0,
                ),
            )
        )


class Selector(PsycheModule):
    module_id = "SELECT"
    stage = PsycheStage.ACTION_SELECTION

    def process(self, context: PsycheContext) -> PsycheOutput:
        return PsycheOutput(
            selection=PsycheSelection(
                source_module=self.module_id,
                action=context.candidates[0].action,
                reason="TEST",
                score=1.0,
            )
        )


def test_later_stage_sees_earlier_stage_update():
    runtime = PsycheRuntime((WriterA(), LaterReader(), CandidateMaker(), Selector()))
    result = runtime.run(
        tick=0,
        agent_id="A001",
        observation=Observation(data={}),
        state=PsycheState.initial_v01(),
        random_value=0.1,
    )
    assert result.state.working["seen"] == 1
    assert result.action.kind == "GO"


def test_same_stage_conflict_fails_closed():
    runtime = PsycheRuntime((WriterA(), WriterB(), CandidateMaker(), Selector()))
    try:
        runtime.run(
            tick=0,
            agent_id="A001",
            observation=Observation(data={}),
            state=PsycheState.initial_v01(),
            random_value=0.1,
        )
    except PsycheContractError as exc:
        assert "conflict" in str(exc).lower()
    else:
        raise AssertionError("Expected PsycheContractError")
