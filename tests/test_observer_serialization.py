from dataclasses import dataclass

from mechanistic_mind.observer import canonical_json, to_primitive


@dataclass
class Demo:
    z: int
    a: tuple[int, int]


def test_canonical_json_is_key_order_stable():
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}

    assert canonical_json(left) == canonical_json(right)


def test_dataclass_and_tuple_are_serialized():
    value = to_primitive(Demo(z=3, a=(1, 2)))

    assert value == {"z": 3, "a": [1, 2]}


def test_unknown_object_fails_instead_of_silent_stringification():
    class Unknown:
        pass

    try:
        to_primitive(Unknown())
    except TypeError:
        pass
    else:
        raise AssertionError("Expected TypeError for unknown object")
