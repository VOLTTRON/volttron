from zmq.sugar.frame import Frame
from volttron.utils.frame_serialization import deserialize_frames, serialize_frames


def test_can_deserialize_homogeneous_string():
    abc = ["alpha", "beta", "gamma"]
    frames = [Frame(x.encode('utf-8')) for x in abc]

    deserialized = deserialize_frames(frames)

    for r in range(len(abc)):
        assert abc[r] == deserialized[r], f"Element {r} is not the same."


def test_can_serialize_homogeneous_strings():
    original = ["alpha", "beta", "gamma"]
    frames = serialize_frames(original)

    for r in range(len(original)):
        assert original[r] == frames[r].bytes.decode('utf-8'), f"Element {r} is not the same."


def test_mixed_array():
    original = ["alpha", dict(alpha=5, gamma="5.0", theta=5.0), "gamma", ["from", "to", 'VIP1']]
    frames = serialize_frames(original)
    after_deserialize = deserialize_frames(frames)

    for r in range(len(original)):
        assert original[r] == after_deserialize[r], f"Element {r} is not the same."
