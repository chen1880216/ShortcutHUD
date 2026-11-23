"""单实例保护的测试（Windows 命名互斥体）。"""

import unittest
import uuid

from scripts import single_instance
from scripts.single_instance import SingleInstanceGuard


def _unique_name() -> str:
    return rf"Local\ShortcutHUD.Test.{uuid.uuid4().hex}"


class SingleInstanceGuardTests(unittest.TestCase):
    def test_first_guard_acquires_and_second_is_rejected(self) -> None:
        name = _unique_name()
        first = SingleInstanceGuard(name)
        second = SingleInstanceGuard(name)
        try:
            self.assertTrue(first.acquire())
            self.assertFalse(first.already_running)
            self.assertFalse(second.acquire())
            self.assertTrue(second.already_running)
        finally:
            second.release()
            first.release()

    def test_release_allows_a_new_instance(self) -> None:
        name = _unique_name()
        first = SingleInstanceGuard(name)
        third = SingleInstanceGuard(name)
        try:
            self.assertTrue(first.acquire())
            first.release()
            self.assertTrue(third.acquire())
            self.assertFalse(third.already_running)
        finally:
            third.release()

    def test_non_windows_platform_is_a_noop(self) -> None:
        original = single_instance.WINDOWS
        single_instance.WINDOWS = False
        try:
            guard = SingleInstanceGuard(_unique_name())
            self.assertTrue(guard.acquire())
            self.assertFalse(guard.already_running)
            guard.release()
        finally:
            single_instance.WINDOWS = original

    def test_context_manager_releases_lock(self) -> None:
        name = _unique_name()
        with SingleInstanceGuard(name) as guard:
            self.assertTrue(guard.acquire())
            blocked = SingleInstanceGuard(name)
            self.assertFalse(blocked.acquire())
            blocked.release()
        after = SingleInstanceGuard(name)
        try:
            self.assertTrue(after.acquire())
            self.assertFalse(after.already_running)
        finally:
            after.release()


if __name__ == "__main__":
    unittest.main()
