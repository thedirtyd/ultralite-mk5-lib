"""Tests for set-ab-monitor / set-ab-path CLI routing."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ultralite_mk5_lib.commands import apply_set_ab_monitor, apply_set_ab_path


class ABMonitorCliTests(unittest.TestCase):
    def test_set_ab_monitor_on(self) -> None:
        device = MagicMock()
        with patch("ultralite_mk5_lib.ab_monitor.apply_ab_monitor_write") as mock_apply:
            summary = apply_set_ab_monitor(device, "on")
        self.assertEqual(summary, "Set A/B monitor on")
        mock_apply.assert_called_once()

    def test_set_ab_path_both(self) -> None:
        device = MagicMock()
        with patch("ultralite_mk5_lib.ab_monitor.apply_ab_monitor_write") as mock_apply:
            summary = apply_set_ab_path(device, "both")
        self.assertEqual(summary, "Set A/B path to both")
        mock_apply.assert_called_once()


if __name__ == "__main__":
    unittest.main()
