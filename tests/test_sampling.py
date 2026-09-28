import unittest

from multimodal_agents.sampling import (
    TimeInterval,
    fixed_rate_samples,
    interval_observed,
)


class SamplingTests(unittest.TestCase):
    def test_one_fps_misses_planted_subsecond_event(self) -> None:
        event = TimeInterval(1200, 1600)
        samples = fixed_rate_samples(6000, 1)
        self.assertEqual(samples, (0, 1000, 2000, 3000, 4000, 5000))
        self.assertFalse(interval_observed(event, samples))

    def test_five_fps_observes_same_event(self) -> None:
        event = TimeInterval(1200, 1600)
        samples = fixed_rate_samples(6000, 5)
        self.assertTrue(interval_observed(event, samples))

    def test_invalid_sampling_rate_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            fixed_rate_samples(6000, 0)


if __name__ == "__main__":
    unittest.main()
