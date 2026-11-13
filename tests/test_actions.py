import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from jarvis_pc.actions import ActionError, Actions, DryRunActions


def action(kind, value=None):
    return SimpleNamespace(kind=kind, value=value)


class ActionsTests(unittest.TestCase):
    def setUp(self):
        self.platform = patch.object(sys, "platform", "win32")
        self.platform.start()
        self.addCleanup(self.platform.stop)

    @patch("jarvis_pc.actions._endpoint")
    def test_set_volume_uses_scalar_not_decibels(self, endpoint):
        result = Actions().execute(action("volume_set", 35))
        endpoint.return_value.SetMasterVolumeLevelScalar.assert_called_once_with(.35, None)
        self.assertEqual(result, "Громкость: 35%")

    @patch("jarvis_pc.actions._endpoint")
    def test_change_volume_reads_current_and_clamps(self, endpoint):
        endpoint.return_value.GetMasterVolumeLevelScalar.return_value = .95
        Actions().execute(action("volume_change", 10))
        endpoint.return_value.SetMasterVolumeLevelScalar.assert_called_with(1, None)
        endpoint.return_value.GetMasterVolumeLevelScalar.return_value = .05
        Actions().execute(action("volume_change", -10))
        endpoint.return_value.SetMasterVolumeLevelScalar.assert_called_with(0, None)

    @patch("jarvis_pc.actions._endpoint")
    def test_mute_and_unmute_are_explicit_not_toggles(self, endpoint):
        Actions().execute(action("mute"))
        Actions().execute(action("unmute"))
        self.assertEqual(endpoint.return_value.SetMute.call_args_list, [call(1, None), call(0, None)])

    @patch("jarvis_pc.actions._user32")
    def test_minimize_uses_full_foreground_handle(self, native):
        native.return_value.GetForegroundWindow.return_value = 0x123456789
        Actions().execute(action("minimize_window"))
        native.return_value.ShowWindow.assert_called_once_with(0x123456789, 6)

    @patch("jarvis_pc.actions._user32")
    def test_minimize_no_foreground_fails(self, native):
        native.return_value.GetForegroundWindow.return_value = 0
        with self.assertRaises(ActionError):
            Actions().execute(action("minimize_window"))
        native.return_value.ShowWindow.assert_not_called()

    @patch("jarvis_pc.actions._user32")
    def test_minimize_all_releases_both_keys(self, native):
        Actions().execute(action("minimize_all"))
        self.assertEqual(native.return_value.keybd_event.call_args_list, [
            call(0x5B, 0, 0, 0), call(0x4D, 0, 0, 0),
            call(0x4D, 0, 2, 0), call(0x5B, 0, 2, 0),
        ])

    @patch("jarvis_pc.actions._user32")
    def test_minimize_all_releases_keys_when_second_press_fails(self, native):
        native.return_value.keybd_event.side_effect = [None, OSError("failed"), None, None]
        with self.assertRaises(ActionError):
            Actions().execute(action("minimize_all"))
        self.assertEqual(native.return_value.keybd_event.call_args_list[-2:], [
            call(0x4D, 0, 2, 0), call(0x5B, 0, 2, 0),
        ])

    @patch("jarvis_pc.actions._user32")
    def test_lock_checks_windows_result(self, native):
        native.return_value.LockWorkStation.return_value = 0
        with self.assertRaises(ActionError):
            Actions().execute(action("lock"))
        native.return_value.LockWorkStation.return_value = 1
        self.assertEqual(Actions().execute(action("lock")), "Компьютер заблокирован")

    @patch("jarvis_pc.actions._endpoint")
    def test_native_errors_have_clear_context(self, endpoint):
        endpoint.side_effect = OSError("device absent")
        with self.assertRaisesRegex(ActionError, "volume_set"):
            Actions().execute(action("volume_set", 50))

    def test_unsupported_platform(self):
        with patch.object(sys, "platform", "linux"):
            with self.assertRaisesRegex(ActionError, "Windows"):
                Actions().execute(action("lock"))

    @patch("jarvis_pc.actions._endpoint")
    @patch("jarvis_pc.actions._user32")
    def test_dry_run_never_calls_native_code(self, native, endpoint):
        for kind in ("mute", "unmute", "minimize_all", "minimize_window", "lock"):
            self.assertEqual(DryRunActions().execute(action(kind)), f"[dry-run] {kind}")
        self.assertEqual(DryRunActions().execute(action("volume_set", 50)), "[dry-run] volume_set 50")
        native.assert_not_called()
        endpoint.assert_not_called()

    def test_invalid_actions_fail_before_native_calls(self):
        for command in [action("shell"), action("volume_set", 101), action("volume_set", -1),
                        action("volume_change", None), action("volume_set", True)]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                DryRunActions().execute(command)


if __name__ == "__main__":
    unittest.main()
