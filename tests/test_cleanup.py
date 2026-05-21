"""Tests for cmd_queue cleanup helpers."""
from __future__ import annotations


def test_cmd_queue_cleanup_matches_workers_and_monitors():
    from cmd_queue.main import _cmd_queue_tmux_session_ids

    sessions = [
        {'id': 'cmdq_worker_abc', 'rest': '...'},
        {'id': 'cmdq-monitor-worker_abc', 'rest': '...'},
        {'id': 'cmdq-monitor-slurm_abc', 'rest': '...'},
        {'id': 'unrelated', 'rest': '...'},
        {'id': 'my-cmdq-monitor-note', 'rest': '...'},
    ]

    assert _cmd_queue_tmux_session_ids(sessions) == [
        'cmdq_worker_abc',
        'cmdq-monitor-worker_abc',
        'cmdq-monitor-slurm_abc',
    ]


def test_cmd_queue_cleanup_prefix_predicate():
    from cmd_queue.main import _is_cmd_queue_tmux_session_id

    assert _is_cmd_queue_tmux_session_id('cmdq_worker')
    assert _is_cmd_queue_tmux_session_id('cmdq-monitor-worker')
    assert not _is_cmd_queue_tmux_session_id('cmdqmonitor-worker')
    assert not _is_cmd_queue_tmux_session_id('other-cmdq-monitor-worker')
