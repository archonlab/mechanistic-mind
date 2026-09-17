from mechanistic_mind.mechanisms import (
    Mechanism,
    MechanismContext,
    MechanismOutput,
    MechanismRegistry,
)


class Alpha(Mechanism):
    mechanism_id = "B"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput()


class Beta(Mechanism):
    mechanism_id = "A"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput()


def test_registry_execution_order_is_stable():
    registry = MechanismRegistry()
    registry.register(Alpha())
    registry.register(Beta())

    assert [m.mechanism_id for m in registry.ordered()] == ["A", "B"]


def test_duplicate_mechanism_ids_are_rejected():
    registry = MechanismRegistry()
    registry.register(Alpha())

    try:
        registry.register(Alpha())
    except ValueError:
        pass
    else:
        raise AssertionError("Expected duplicate mechanism rejection")
