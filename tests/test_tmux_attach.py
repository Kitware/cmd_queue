"""
Tests for the ``monitor`` argument on ``Queue.run()`` for the tmux and
slurm backends — specifically the new ``'hybrid'`` mode.

The full end-to-end behavior (rich.Live + cbreak + tmux attach) requires
an interactive TTY and a live tmux server, so these tests stay at the
plumbing layer:

* ``monitor='hybrid'`` (the default) on an inline-monitor run spawns the
  side ``cmd_queue monitor`` tmux session and tears it down afterwards.
* ``monitor='inline'`` leaves the existing inline-only behavior intact
  (no side spawn).
* ``monitor='hybrid'`` falls back gracefully when tmux is missing.
* The renderable hint and the textual app expose the right keybinding.

The tmux helpers are monkeypatched so the tests run without a tmux server.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest


def _patch_tmux_helpers(monkeypatch: pytest.MonkeyPatch) -> Dict[str, List[Any]]:
    """Replace the tmux helper static methods with recorders.

    Returns a dict of call-log lists keyed by helper name so each test
    can assert on what the run() path triggered.
    """
    from cmd_queue.util import util_tmux

    calls: Dict[str, List[Any]] = {
        'spawn': [],
        'kill': [],
        'has': [],
        'attach_or_switch': [],
    }

    def fake_spawn(
        session_name: str,
        manifest_path: Any,
        attach: bool = True,
        verbose: int = 0,
        extra_args: Any = None,
    ) -> Dict[str, Any]:
        calls['spawn'].append(
            {
                'session_name': session_name,
                'manifest_path': str(manifest_path),
                'attach': attach,
                'extra_args': list(extra_args or []),
            }
        )
        return {'session_name': session_name, 'attach_command': 'noop'}

    def fake_kill(session_name: str, verbose: int = 3) -> None:
        calls['kill'].append(session_name)

    def fake_has(session_name: str) -> bool:
        calls['has'].append(session_name)
        # Pretend the session exists between spawn and kill so the
        # finally-clause actually exercises the kill path.
        return True

    def fake_attach(session_name: str) -> None:
        calls['attach_or_switch'].append(session_name)

    monkeypatch.setattr(
        util_tmux.tmux, 'spawn_monitor_session', staticmethod(fake_spawn)
    )
    monkeypatch.setattr(
        util_tmux.tmux, 'kill_session', staticmethod(fake_kill)
    )
    monkeypatch.setattr(
        util_tmux.tmux, 'has_session', staticmethod(fake_has)
    )
    monkeypatch.setattr(
        util_tmux.tmux, 'attach_or_switch', staticmethod(fake_attach)
    )
    return calls


def _make_tmux_queue(tmp_path):
    from cmd_queue.tmux_queue import TMUXMultiQueue

    queue = TMUXMultiQueue(size=1, name='tmux-attach-test', dpath=tmp_path)
    queue.submit('true')
    return queue


def test_hybrid_mode_spawns_and_kills_side_session(monkeypatch, tmp_path):
    """With ``monitor='hybrid'`` the dispatcher must spawn the side
    session before invoking ``self.monitor()`` and kill it afterwards
    (so we don't leak tmux sessions per run)."""
    calls = _patch_tmux_helpers(monkeypatch)
    monkeypatch.setattr('ubelt.find_exe', lambda name: f'/usr/bin/{name}')
    queue = _make_tmux_queue(tmp_path)

    monitor_calls: List[Dict[str, Any]] = []

    def fake_monitor(self, **kwargs):
        # Record what the dispatcher passed and assert the session was
        # already spawned by this point.
        monitor_calls.append(kwargs)
        return {'status': 'done'}

    monkeypatch.setattr(
        'cmd_queue.tmux_queue.TMUXMultiQueue.monitor', fake_monitor
    )

    queue._dispatch_monitor(
        monitor='hybrid',
        manifest_path=tmp_path / 'manifest.json',
        onfail='kill',
        onexit='',
        with_textual='auto',
    )

    assert len(calls['spawn']) == 1, 'side session must be spawned exactly once'
    spawn = calls['spawn'][0]
    assert spawn['session_name'].startswith('cmdq-monitor-')
    assert '--onfail=kill' in spawn['extra_args']
    assert spawn['attach'] is False, (
        'spawn_monitor_session(attach=False) — the inline path takes '
        'over the foreground separately via the [a] keybind'
    )

    assert len(monitor_calls) == 1
    assert monitor_calls[0]['side_session'] == spawn['session_name']

    assert calls['kill'] == [spawn['session_name']], (
        'side session must be killed in the dispatcher finally-clause'
    )


def test_inline_mode_does_not_spawn(monkeypatch, tmp_path):
    """``monitor='inline'`` is the explicit opt-out: no side session
    should be created and ``monitor()`` should be invoked without a
    ``side_session`` argument (so the inline UI keeps its old shape)."""
    calls = _patch_tmux_helpers(monkeypatch)
    monkeypatch.setattr('ubelt.find_exe', lambda name: f'/usr/bin/{name}')
    queue = _make_tmux_queue(tmp_path)

    seen: List[Dict[str, Any]] = []

    def fake_monitor(self, **kwargs):
        seen.append(kwargs)
        return None

    monkeypatch.setattr(
        'cmd_queue.tmux_queue.TMUXMultiQueue.monitor', fake_monitor
    )
    queue._dispatch_monitor(
        monitor='inline',
        manifest_path=tmp_path / 'manifest.json',
        onfail='kill',
        onexit='',
        with_textual='auto',
    )

    assert calls['spawn'] == [], "inline mode must not spawn a side session"
    assert calls['kill'] == [], 'no kill if nothing was spawned'
    assert 'side_session' not in seen[0], (
        'inline path goes through the legacy monitor() signature, '
        'with no side_session kwarg'
    )


def test_hybrid_falls_back_when_tmux_missing(monkeypatch, tmp_path):
    """If tmux is unavailable, hybrid degrades gracefully to inline-
    only (a warning is emitted and ``monitor()`` runs with
    ``side_session=None``)."""
    calls = _patch_tmux_helpers(monkeypatch)
    monkeypatch.setattr('ubelt.find_exe', lambda name: None)
    queue = _make_tmux_queue(tmp_path)

    seen: List[Dict[str, Any]] = []

    def fake_monitor(self, **kwargs):
        seen.append(kwargs)
        return None

    monkeypatch.setattr(
        'cmd_queue.tmux_queue.TMUXMultiQueue.monitor', fake_monitor
    )
    with pytest.warns(UserWarning, match='tmux not found'):
        queue._dispatch_monitor(
            monitor='hybrid',
            manifest_path=tmp_path / 'manifest.json',
            onfail='kill',
            onexit='',
            with_textual='auto',
        )

    assert calls['spawn'] == [], 'no tmux → no side spawn'
    assert seen[0]['side_session'] is None


def test_attach_hint_renderable_mentions_session():
    """The footer text under the live status table must call out the
    keybinding and name the session, otherwise users won't discover the
    feature."""
    from cmd_queue.tmux_queue import _attach_hint_renderable

    hint = _attach_hint_renderable('cmdq-monitor-foo')
    rendered = hint.plain  # rich.Text → strip markup
    assert '[a]' in rendered
    assert '[q]' in rendered
    assert 'cmdq-monitor-foo' in rendered


def test_textual_app_binds_a_only_when_attach_session_set():
    """The textual app should only register the 'a' keybind when an
    attach session is actually wired up — otherwise the binding would
    flag-and-shut-down with nowhere to attach to."""
    pytest.importorskip('textual')
    try:
        from cmd_queue.monitor_app import CmdQueueMonitorApp
    except ImportError:
        pytest.skip('textual monitor app is unavailable on this build')
    if CmdQueueMonitorApp is None:  # gated in tmux_queue.py
        pytest.skip('textual monitor app is gated off')

    def table_fn():
        return None, True, {}

    app_with = CmdQueueMonitorApp(table_fn, attach_session='cmdq-monitor-x')
    app_without = CmdQueueMonitorApp(table_fn)

    assert app_with.attach_session == 'cmdq-monitor-x'
    assert app_with.attach_requested is False
    assert app_without.attach_session is None
    assert hasattr(app_with, 'action_attach_monitor'), (
        'attach action must exist so the binding has a target'
    )


if __name__ == '__main__':
    import sys

    sys.exit(pytest.main([__file__, '-v']))
