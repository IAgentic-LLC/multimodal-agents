from multimodal_agents.tenant_detection import DetectedObject, describe_detections


def test_describe_detections_with_no_objects():
    assert "no objects" in describe_detections([])


def test_describe_detections_counts_and_sorts_by_class_name():
    detections = [
        DetectedObject("person", 0.9, (0, 0, 1, 1)),
        DetectedObject("bus", 0.8, (0, 0, 1, 1)),
        DetectedObject("person", 0.7, (0, 0, 1, 1)),
    ]
    description = describe_detections(detections)
    assert "2 person" in description
    assert "1 bus" in description
    assert description.index("1 bus") < description.index("2 person")
