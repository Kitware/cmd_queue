"""
Conflicting-tmux-session handling.

The behaviour pinned down here exists because an unattended run blocked
forever on a y/n prompt nobody was there to answer, having done no work.
"""
from unittest import mock


def _panes(*commands, dead=False):
    return [
        {'pane_dead': '1' if dead else '0', 'pane_current_command': c}
        for c in commands
    ]


def test_a_session_at_a_shell_prompt_is_not_busy():
    """A finished worker returns to its shell; that session is inert."""
    from cmd_queue.backends import tmux as tmux_mod

    with mock.patch.object(tmux_mod.tmux, 'list_panes',
                           return_value=_panes('bash', 'zsh')):
        assert tmux_mod.session_is_busy('sess') is False


def test_a_session_running_a_command_is_busy():
    from cmd_queue.backends import tmux as tmux_mod

    with mock.patch.object(tmux_mod.tmux, 'list_panes',
                           return_value=_panes('bash', 'python')):
        assert tmux_mod.session_is_busy('sess') is True


def test_a_dead_pane_does_not_count_as_busy():
    from cmd_queue.backends import tmux as tmux_mod

    with mock.patch.object(tmux_mod.tmux, 'list_panes',
                           return_value=_panes('python', dead=True)):
        assert tmux_mod.session_is_busy('sess') is False


def test_unreadable_panes_are_treated_as_busy():
    """The safe error is to leave a session alone, not to kill it."""
    from cmd_queue.backends import tmux as tmux_mod

    with mock.patch.object(tmux_mod.tmux, 'list_panes',
                           side_effect=OSError('no tmux')):
        assert tmux_mod.session_is_busy('sess') is True
    with mock.patch.object(tmux_mod.tmux, 'list_panes', return_value=[]):
        assert tmux_mod.session_is_busy('sess') is True


def test_is_interactive_requires_a_terminal_not_merely_a_stdin():
    """has_stdin() is true under nohup/cron/pipes; is_interactive() is not."""
    import sys

    from cmd_queue.backends import tmux as tmux_mod

    with mock.patch.object(sys, 'stdin', mock.Mock(isatty=lambda: True)), \
         mock.patch.object(sys, 'stdout', mock.Mock(isatty=lambda: True)):
        assert tmux_mod.is_interactive() is True

    # A pipe on either end means nobody can answer a prompt.
    with mock.patch.object(sys, 'stdin', mock.Mock(isatty=lambda: False)), \
         mock.patch.object(sys, 'stdout', mock.Mock(isatty=lambda: True)):
        assert tmux_mod.is_interactive() is False
    with mock.patch.object(sys, 'stdin', mock.Mock(isatty=lambda: True)), \
         mock.patch.object(sys, 'stdout', mock.Mock(isatty=lambda: False)):
        assert tmux_mod.is_interactive() is False


def test_auto_never_asks_when_there_is_no_terminal():
    """The regression that matters: an overnight run must not prompt."""
    from cmd_queue.backends import tmux as tmux_mod

    queue = mock.Mock()
    resolved = {}
    queue.kill_other_queues = lambda ask_first: resolved.update(
        ask_first=ask_first)

    with mock.patch.object(tmux_mod, 'is_interactive', return_value=False):
        tmux_mod.TMUXMultiQueue.handle_other_sessions(queue, 'auto')
    assert resolved['ask_first'] is False

    with mock.patch.object(tmux_mod, 'is_interactive', return_value=True):
        tmux_mod.TMUXMultiQueue.handle_other_sessions(queue, 'auto')
    assert resolved['ask_first'] is True


def test_non_interactive_forces_kill_even_on_a_terminal():
    from cmd_queue.backends import tmux as tmux_mod

    queue = mock.Mock()
    resolved = {}
    queue.kill_other_queues = lambda ask_first: resolved.update(
        ask_first=ask_first)

    with mock.patch.object(tmux_mod, 'is_interactive', return_value=True):
        tmux_mod.TMUXMultiQueue.handle_other_sessions(
            queue, 'auto', non_interactive=True)
    assert resolved['ask_first'] is False


def test_idle_sessions_are_reclaimed_without_asking():
    """Only a session with live work is worth interrupting someone over."""
    from cmd_queue.backends import tmux as tmux_mod

    queue = mock.Mock()
    queue._tmux_session_prefix = 'cmdq_'
    queue.name = 'demo'
    queue.cmd_verbose = 0
    queue._tmux_current_sessions = lambda: [
        {'id': 'cmdq_demo_000_old'},      # finished run
        {'id': 'cmdq_demo_000_live'},     # still working
        {'id': 'cmdq_other_000_x'},       # different queue, untouched
    ]
    killed = []
    busy = {'cmdq_demo_000_live'}

    with mock.patch.object(tmux_mod, 'session_is_busy',
                           side_effect=lambda s: s in busy), \
         mock.patch.object(tmux_mod.ub, 'cmd',
                           side_effect=lambda c, **kw: killed.append(c)), \
         mock.patch('rich.prompt.Confirm.ask', return_value=False) as ask:
        tmux_mod.TMUXMultiQueue.kill_other_queues(queue, ask_first=True)

    # The idle one goes without a question; the busy one is offered and,
    # since the answer was no, survives.
    assert any('cmdq_demo_000_old' in c for c in killed)
    assert not any('cmdq_demo_000_live' in c for c in killed)
    assert not any('cmdq_other_000_x' in c for c in killed)
    assert ask.called


def test_no_prompt_at_all_when_every_other_session_is_idle():
    """The common case must be silent: nothing running, nothing to ask."""
    from cmd_queue.backends import tmux as tmux_mod

    queue = mock.Mock()
    queue._tmux_session_prefix = 'cmdq_'
    queue.name = 'demo'
    queue.cmd_verbose = 0
    queue._tmux_current_sessions = lambda: [{'id': 'cmdq_demo_000_old'}]

    with mock.patch.object(tmux_mod, 'session_is_busy', return_value=False), \
         mock.patch.object(tmux_mod.ub, 'cmd'), \
         mock.patch('rich.prompt.Confirm.ask') as ask:
        tmux_mod.TMUXMultiQueue.kill_other_queues(queue, ask_first=True)

    assert not ask.called
