"""
Regression tests for the blocking-monitor timeout policy.

Production queues can legitimately run for days or weeks, so the blocking
monitor loops must wait forever by default. To keep a stuck worker from
hanging the test suite (or slowly growing pytest's captured output until
the runner is OOM-killed), a finite bound is imposed *only* when running
under pytest, detected via the ``PYTEST_CURRENT_TEST`` env var.

These tests exercise :func:`cmd_queue.util.util_tmux.resolve_block_timeout`
and :func:`cmd_queue.util.util_tmux.block_deadline` directly. Note that
because the suite itself runs under pytest, ``PYTEST_CURRENT_TEST`` is
already set in the environment; the "production" cases delete it via
``monkeypatch`` (which restores it after each test).
"""
from __future__ import annotations

import time

import pytest

from cmd_queue.util.util_tmux import block_deadline, resolve_block_timeout


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start each case from a known-clean env."""
    monkeypatch.delenv('PYTEST_CURRENT_TEST', raising=False)
    monkeypatch.delenv('CMD_QUEUE_BLOCK_TIMEOUT', raising=False)
    monkeypatch.delenv('CMD_QUEUE_PYTEST_BLOCK_TIMEOUT', raising=False)


def test_production_default_is_infinite(monkeypatch):
    # No pytest marker and no override => wait forever.
    _clear_env(monkeypatch)
    assert resolve_block_timeout() is None


def test_pytest_default_is_bounded(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'test_x.py::test_y (call)')
    assert resolve_block_timeout() == 300.0


def test_pytest_default_is_configurable(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'test_x.py::test_y (call)')
    monkeypatch.setenv('CMD_QUEUE_PYTEST_BLOCK_TIMEOUT', '42')
    assert resolve_block_timeout() == 42.0


def test_env_var_overrides_in_production(monkeypatch):
    # A production user can opt into a bound without pytest involved.
    _clear_env(monkeypatch)
    monkeypatch.setenv('CMD_QUEUE_BLOCK_TIMEOUT', '5')
    assert resolve_block_timeout() == 5.0


def test_env_var_overrides_pytest_default(monkeypatch):
    # The explicit env var beats the pytest auto-default, in both directions.
    _clear_env(monkeypatch)
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'test_x.py::test_y (call)')
    monkeypatch.setenv('CMD_QUEUE_BLOCK_TIMEOUT', '5')
    assert resolve_block_timeout() == 5.0


@pytest.mark.parametrize('word', ['none', 'inf', 'infinite', 'forever', 'NONE'])
def test_env_var_can_force_infinite_under_pytest(monkeypatch, word):
    _clear_env(monkeypatch)
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'test_x.py::test_y (call)')
    monkeypatch.setenv('CMD_QUEUE_BLOCK_TIMEOUT', word)
    assert resolve_block_timeout() is None


def test_explicit_arg_wins(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('CMD_QUEUE_BLOCK_TIMEOUT', '5')
    assert resolve_block_timeout(12) == 12.0
    # 0 and inf mean "wait forever".
    assert resolve_block_timeout(0) is None
    assert resolve_block_timeout(float('inf')) is None


def test_explicit_auto_falls_through(monkeypatch):
    # 'auto' is treated like None so callers can pass it as a sentinel.
    _clear_env(monkeypatch)
    assert resolve_block_timeout('auto') is None
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'test_x.py::test_y (call)')
    assert resolve_block_timeout('auto') == 300.0


def test_block_deadline_is_noop_when_infinite(monkeypatch):
    _clear_env(monkeypatch)
    check = block_deadline(label='queue forever')
    # Even after time passes, an infinite deadline never raises.
    for _ in range(3):
        time.sleep(0.001)
        assert check() is None


def test_block_deadline_raises_after_expiry(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('CMD_QUEUE_BLOCK_TIMEOUT', '0.01')
    check = block_deadline(label='queue stuck')
    # Not yet expired right after construction.
    check()
    time.sleep(0.05)
    with pytest.raises(TimeoutError, match='queue stuck'):
        check()


if __name__ == '__main__':
    import sys

    sys.exit(pytest.main([__file__, '-v']))
