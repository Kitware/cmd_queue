"""
Test that ``Queue.submit(..., log=True)`` plumbs the flag through to the
underlying ``BashJob`` and that the finalized script tees the command.

This is the integration boundary: ``test_bash_variants.py`` covers
``BashJob`` directly (i.e. the renderer), but downstream callers
(kwdagger and others) reach ``BashJob`` only via ``Queue.submit(...)``.
A regression where ``submit`` drops or shadows the ``log`` kwarg would
silently disable tee logging without any other test catching it, which
is exactly the kind of thing this test is here to catch.
"""
import cmd_queue


def _command_section(text: str) -> str:
    """Return the slice of ``text`` between the ``# command:`` marker and
    the ``# after_command:`` marker. Lets the assertion focus on the
    actual job command and not bookkeeping lines that may also contain
    paths the test doesn't care about.
    """
    start = text.find('# command:')
    end = text.find('# after_command:')
    if start == -1 or end == -1:
        return text
    return text[start:end]


def test_submit_with_log_true_produces_tee():
    queue = cmd_queue.Queue.create(backend='serial', name='log-flag-true', size=1)
    job = queue.submit('echo hi', name='job1', log=True)

    assert job.log is True, 'log=True should land on BashJob.log'

    text = job.finalize_text(with_status=True, with_gaurds=True)
    cmd = _command_section(text)

    assert '| tee ' in cmd, (
        'Queue.submit(log=True) should produce a tee in the rendered '
        'command section. Got:\n' + cmd
    )
    assert str(job.log_fpath) in cmd, (
        'Tee target must be the BashJob.log_fpath so log inspection '
        'tools find it. Got:\n' + cmd
    )


def test_submit_with_log_false_omits_tee():
    queue = cmd_queue.Queue.create(backend='serial', name='log-flag-false', size=1)
    job = queue.submit('echo hi', name='job1', log=False)

    assert job.log is False, 'log=False should land on BashJob.log'

    text = job.finalize_text(with_status=True, with_gaurds=True)
    cmd = _command_section(text)

    assert '| tee ' not in cmd, (
        'Queue.submit(log=False) must NOT add a tee to the command. '
        'Got:\n' + cmd
    )


def test_submit_log_default_omits_tee():
    """The current ``BashJob`` default is ``log=False`` for backward
    compatibility. If a caller does not pass ``log``, no tee should
    appear. Tracked here so any default flip is caught explicitly.
    """
    queue = cmd_queue.Queue.create(backend='serial', name='log-flag-default', size=1)
    job = queue.submit('echo hi', name='job1')

    assert job.log is False, 'BashJob.log default is False'

    text = job.finalize_text(with_status=True, with_gaurds=True)
    cmd = _command_section(text)
    assert '| tee ' not in cmd, (
        'Default Queue.submit (no log kwarg) must NOT tee. Got:\n' + cmd
    )


if __name__ == '__main__':
    test_submit_with_log_true_produces_tee()
    test_submit_with_log_false_omits_tee()
    test_submit_log_default_omits_tee()
    print('All submit log-flag tests passed.')
