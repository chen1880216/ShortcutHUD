"""Modifier-to-resolver orchestration for the compact ShortcutHUD window."""

from __future__ import annotations

import time
from collections.abc import Mapping
from copy import deepcopy
from typing import Protocol

from PySide6.QtCore import QObject, QTimer, Slot

from .application_descriptor import ApplicationDescriptorFactory
from .catalog_application_registry import CatalogApplicationRegistry
from .hud_entry_limits import (
    DEFAULT_SHOW_ALL_SHORTCUTS,
    SHOW_ALL_SHORTCUTS_SETTING,
)
from .modifier_state import canonicalize_modifier_state
from .shortcut_catalog import ShortcutCatalog
from .shortcut_catalog_resolver import CatalogShortcutResolver
from .shortcut_resolver import ShortcutEntry
from .suppression_policy import PresentationIntent, SuppressionPolicy


class _ConfigProvider(Protocol):
    def get_all_shortcuts(self) -> dict[str, object]: ...

    def get_setting(self, key: str, default: object = None) -> object: ...


class _ForegroundState(Protocol):
    current_app_name: str | None
    identity_pending: bool


class _HudView(Protocol):
    def isVisible(self) -> bool: ...

    def hide(self) -> None: ...

    def show_hud(self) -> None: ...

    def apply_opacity(self, percent: float | int | None) -> None: ...

    def set_entries(
        self,
        application_name: str,
        modifier_combination: str,
        entries: list[ShortcutEntry],
        language: str | None,
        application_display_name: str | None = None,
        *,
        show_all: bool = False,
    ) -> None: ...

    def set_sections(
        self,
        application_name: str,
        sections: list[tuple[str, list[ShortcutEntry]]],
        language: str | None,
        application_display_name: str | None = None,
        header_suffix: str = "",
        *,
        show_all: bool = False,
    ) -> None: ...


class _WinDiscoveryProxy(Protocol):
    def current_physical_win_vk(self) -> int | None: ...

    def activate_for_current_hold(self, win_vk: int) -> bool: ...


class ShortcutHudController(QObject):
    """Resolve modifier state and update one persistent HUD view."""

    DEFAULT_SHOW_DELAY_MS = 150
    WIN_ONLY_SHOW_DELAY_MS = 300
    # The explicit all-groups command must survive the release of its own
    # chord: modifier events arriving inside this window are not new holds.
    SECTIONS_GRACE_SECONDS = 0.35
    ALL_GROUPS_MODIFIERS = ("Ctrl", "Alt", "Shift")
    _MODIFIER_KEY_NAMES = frozenset({"ctrl", "alt", "shift", "win"})

    def __init__(
        self,
        config_manager: _ConfigProvider,
        foreground_monitor: _ForegroundState,
        hud_window: _HudView,
        win_discovery_proxy: _WinDiscoveryProxy,
        parent: QObject | None = None,
        show_delay_ms: int = DEFAULT_SHOW_DELAY_MS,
        win_only_show_delay_ms: int = WIN_ONLY_SHOW_DELAY_MS,
        user_profiles: Mapping[str, object] | None = None,
        suppression_policy: SuppressionPolicy | None = None,
        selection_store: object | None = None,
    ) -> None:
        super().__init__(parent)
        self._config_manager = config_manager
        self._foreground_monitor = foreground_monitor
        self._hud_window = hud_window
        self._win_discovery_proxy = win_discovery_proxy
        self._user_profiles: dict[str, object] = (
            deepcopy(dict(user_profiles))
            if isinstance(user_profiles, Mapping)
            else {}
        )
        self._suppression_policy = suppression_policy or SuppressionPolicy()
        self._selection_store = selection_store
        self._current_modifier: str | None = None
        self._show_delay_ms = show_delay_ms
        self._win_only_show_delay_ms = win_only_show_delay_ms
        self._identity_delay_elapsed = False
        self._suppression_rearm_required = False
        self._sections_active = False
        self._sections_grace_until = 0.0

        self._guide_active = False

        self._win_modifier_held = False
        self._win_activation_attempted = False
        self._win_discovery_active = False
        self._win_execution_seen = False

        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._show_pending_hud)

    @Slot(set)
    def on_modifiers_changed(self, modifiers: set[str]) -> None:
        """Schedule, update, or hide the HUD for the latest logical state."""

        if self._sections_active:
            if time.monotonic() < self._sections_grace_until:
                return
            self._end_sections()

        self._identity_delay_elapsed = False
        win_held = self._contains_win_modifier(modifiers)
        if win_held and not self._win_modifier_held:
            self._reset_win_discovery_state()
        elif not win_held:
            self._reset_win_discovery_state()
        self._win_modifier_held = win_held

        self._current_modifier = canonicalize_modifier_state(modifiers)
        if self._current_modifier is None:
            self._suppression_rearm_required = False
        elif not self._policy_allows_quick_hud():
            self._suppression_rearm_required = True
        self.refresh_current_state()

    @Slot(str, str)
    def on_key_event(self, key_name: str, event_type: str) -> None:
        """Hide an active Win discovery HUD once real shortcut execution starts."""

        if (
            self._sections_active
            and isinstance(key_name, str)
            and isinstance(event_type, str)
            and event_type.casefold() == "down"
            and key_name.casefold() == "esc"
        ):
            self._end_sections()
            return

        if (
            not self._win_discovery_active
            or not isinstance(key_name, str)
            or not isinstance(event_type, str)
            or event_type.casefold() != "down"
            or key_name.casefold() in self._MODIFIER_KEY_NAMES
        ):
            return

        self._win_execution_seen = True
        self._cancel_and_hide()

    @Slot()
    def show_all_groups(self) -> None:
        """List the Ctrl, Alt and Shift groups of the frontmost app together.

        This is the explicit-command counterpart of the passive HUD: it does
        not depend on holding a modifier, and it stays up until the user
        presses a modifier again or dismisses it with Esc.
        """

        if not self._policy_allows_quick_hud():
            return

        sections = self._resolve_all_sections()
        if not sections:
            self._end_sections()
            return

        self._show_timer.stop()
        self._identity_delay_elapsed = False
        self._sections_active = True
        self._sections_grace_until = (
            time.monotonic() + self.SECTIONS_GRACE_SECONDS
        )
        app_name = self._foreground_monitor.current_app_name
        language = self._language()
        self._hud_window.apply_opacity(self._window_opacity())
        self._hud_window.set_sections(
            self._application_key(),
            sections,
            language,
            self._application_display_name(
                self._current_catalog(), app_name, language
            ),
            self.tr("All shortcuts"),
            show_all=self._show_all_shortcuts(),
        )
        self._hud_window.show_hud()

    @Slot(str)
    def on_active_app_changed(self, _application_name: str) -> None:
        """Refresh from ForegroundMonitor's already-maintained current state."""

        if self._current_modifier is not None:
            self.refresh_current_state()

    def refresh_current_state(self) -> None:
        """Re-resolve the latest state without querying foreground Windows."""

        if self._sections_active:
            return

        if not self._quick_hud_is_allowed():
            self._cancel_and_hide()
            return

        if self._current_modifier is None:
            self._cancel_and_hide()
            return

        entries = self._resolve_current_entries()
        if not entries:
            if self._is_identity_pending():
                self._hud_window.hide()
                if (
                    not self._show_timer.isActive()
                    and not self._identity_delay_elapsed
                ):
                    self._start_show_timer()
                return
            self._cancel_and_hide()
            return

        if self._win_discovery_active and self._win_execution_seen:
            self._cancel_and_hide()
            return
        if self._identity_delay_elapsed:
            self._identity_delay_elapsed = False
            self._show_pending_hud()
            return


        if self._current_modifier == "Win" and not self._win_discovery_active:
            self._show_timer.stop()
            self._hud_window.hide()
            if not self._win_activation_attempted:
                self._start_show_timer()
            return

        if self._hud_window.isVisible():
            self._show_timer.stop()
            self._render(entries)
            return

        self._start_show_timer()

    def stop(self) -> None:
        """Clear controller work; the application owns the proxy lifecycle."""

        self._current_modifier = None
        self._suppression_rearm_required = False
        self._sections_active = False
        self._sections_grace_until = 0.0
        self._win_modifier_held = False
        self._reset_win_discovery_state()
        self._cancel_and_hide()

    def update_user_profiles(self, profiles: Mapping[str, object] | None) -> None:
        """Replace the in-memory USER_APP snapshot for a future editor reload."""

        self._user_profiles = (
            deepcopy(dict(profiles)) if isinstance(profiles, Mapping) else {}
        )
        self.refresh_current_state()

    def on_suppression_changed(self) -> None:
        """Apply a policy change immediately to pending or visible HUD work."""

        if not self._policy_allows_quick_hud():
            if self._current_modifier is not None:
                self._suppression_rearm_required = True
            self._cancel_and_hide()
            return
        self.refresh_current_state()

    def set_guide_active(self, active: bool) -> None:
        """Suspend passive presentation until a fresh post-Guide key hold."""
        self._guide_active = active
        self._sections_active = False
        self._sections_grace_until = 0.0
        self._suppression_rearm_required = self._current_modifier is not None
        self._reset_win_discovery_state()
        self._cancel_and_hide()

    def _show_pending_hud(self) -> None:
        if not self._quick_hud_is_allowed():
            self._cancel_and_hide()
            return
        if self._current_modifier is None:
            return

        entries = self._resolve_current_entries()
        if not entries:
            self._hud_window.hide()
            if self._is_identity_pending():
                self._identity_delay_elapsed = True
            else:
                self._identity_delay_elapsed = False
            return

        if self._current_modifier == "Win":
            if self._win_activation_attempted or self._win_execution_seen:
                self._hud_window.hide()
                return
            self._win_activation_attempted = True

            win_vk = self._current_physical_win_vk()
            if win_vk is None or not self._activate_win_proxy(win_vk):
                self._hud_window.hide()
                return
            self._win_discovery_active = True

        self._identity_delay_elapsed = False
        self._render(entries)
        self._hud_window.show_hud()

    def _resolve_current_entries(self) -> list[ShortcutEntry]:
        catalog = self._current_catalog()
        return CatalogShortcutResolver(catalog).resolve(
            self._foreground_monitor.current_app_name,
            self._current_modifier,
            self._user_profiles,
            self._selection_store,
            self._language(),
        )

    def _resolve_all_sections(self) -> list[tuple[str, list[ShortcutEntry]]]:
        resolver = CatalogShortcutResolver(self._current_catalog())
        sections: list[tuple[str, list[ShortcutEntry]]] = []
        for modifier in self.ALL_GROUPS_MODIFIERS:
            entries = resolver.resolve(
                self._foreground_monitor.current_app_name,
                modifier,
                self._user_profiles,
                self._selection_store,
                self._language(),
            )
            if entries:
                sections.append((modifier, entries))
        return sections

    def _application_key(self) -> str:
        app_name = self._foreground_monitor.current_app_name
        return app_name.upper() if app_name else "DEFAULT"

    def _render(self, entries: list[ShortcutEntry]) -> None:
        app_name = self._foreground_monitor.current_app_name
        language = self._language()
        self._hud_window.apply_opacity(self._window_opacity())
        self._hud_window.set_entries(
            self._application_key(),
            self._current_modifier or "",
            entries,
            language,
            self._application_display_name(self._current_catalog(), app_name, language),
            show_all=self._show_all_shortcuts(),
        )

    def _end_sections(self) -> None:
        """Drop the all-groups panel and require a fresh hold to show it again."""

        self._sections_active = False
        self._sections_grace_until = 0.0
        self._suppression_rearm_required = self._current_modifier is not None
        self._cancel_and_hide()

    def _show_all_shortcuts(self) -> bool:
        value = self._config_manager.get_setting(
            SHOW_ALL_SHORTCUTS_SETTING,
            DEFAULT_SHOW_ALL_SHORTCUTS,
        )
        return value if isinstance(value, bool) else DEFAULT_SHOW_ALL_SHORTCUTS

    def _window_opacity(self) -> float | None:
        """Read the overlay opacity percentage (``None`` keeps the default)."""

        value = self._config_manager.get_setting("opacity", None)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    def _current_catalog(self) -> ShortcutCatalog:
        catalog_getter = getattr(self._config_manager, "get_shortcut_catalog", None)
        return (
            catalog_getter()
            if callable(catalog_getter)
            else ShortcutCatalog.from_legacy_shortcuts(
                self._config_manager.get_all_shortcuts()
            )
        )

    def _language(self) -> str:
        language_setting = self._config_manager.get_setting("language", "en_US")
        return language_setting if isinstance(language_setting, str) else "en_US"

    def _application_display_name(
        self,
        catalog: ShortcutCatalog,
        application_name: str | None,
        language: str,
    ) -> str:
        record = CatalogApplicationRegistry(
            catalog, self._user_profiles, language
        ).find_by_identity(application_name)
        if record is not None:
            return record.display_name
        descriptor = ApplicationDescriptorFactory().describe(application_name)
        return descriptor.display_name if descriptor is not None else "DEFAULT"

    def _cancel_and_hide(self) -> None:
        self._show_timer.stop()
        self._hud_window.hide()

        self._identity_delay_elapsed = False

    def _start_show_timer(self) -> None:
        if not self._quick_hud_is_allowed() or self._show_timer.isActive():
            return
        delay = (
            self._win_only_show_delay_ms
            if self._current_modifier == "Win"
            else self._show_delay_ms
        )
        self._show_timer.setInterval(delay)
        self._show_timer.start()

    def _quick_hud_is_allowed(self) -> bool:
        return (
            not self._suppression_rearm_required
            and self._policy_allows_quick_hud()
        )

    def _policy_allows_quick_hud(self) -> bool:
        return not self._guide_active and self._suppression_policy.allows(PresentationIntent.PASSIVE)

    def _is_identity_pending(self) -> bool:
        return bool(getattr(self._foreground_monitor, "identity_pending", False))

    def _current_physical_win_vk(self) -> int | None:
        try:
            return self._win_discovery_proxy.current_physical_win_vk()
        except Exception:
            return None

    def _activate_win_proxy(self, win_vk: int) -> bool:
        try:
            return self._win_discovery_proxy.activate_for_current_hold(win_vk)
        except Exception:
            return False

    def _reset_win_discovery_state(self) -> None:
        self._win_activation_attempted = False
        self._win_discovery_active = False
        self._win_execution_seen = False

    @staticmethod
    def _contains_win_modifier(modifiers: set[str]) -> bool:
        return any(
            isinstance(modifier, str) and modifier.casefold() == "win"
            for modifier in modifiers
        )
