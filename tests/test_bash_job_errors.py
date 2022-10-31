import ubelt as ub


def demo_script(dpath):
    script_fpath = (dpath / 'myprog.py')
    script_fpath.write_text(ub.codeblock(
        '''
        #!/usr/env/python

        def main():
            import argparse
            import ubelt as ub
            parser = argparse.ArgumentParser()
            parser.add_argument('--steps', type=int, default=0)
            parser.add_argument('--steptime', type=float, default=1)
            parser.add_argument('--failflag', action='store_true')
            args = parser.parse_args()
            print('I am just a simple script')
            print(f'args.__dict__={args.__dict__}')

            import time
            if args.steps:
                for _ in ub.ProgIter(range(args.steps), desc='working'):
                    time.sleep(args.steptime)

            if args.failflag:
                print('Oh no, I will fail')
                raise Exception('I failed')
            print('I did not fail. Yay!')

        if __name__ == '__main__':
            main()
        '''))
    return script_fpath


def test_bash_job_errors():
    import ubelt as ub
    dpath = ub.Path.appdir('cmd_queue', 'tests', 'test_bash_job_errors')
    dpath.delete().ensuredir()
    from cmd_queue.serial_queue import BashJob
    # Demo full boilerplate for a job with no dependencies
    import sys
    sys.executable

    script_fpath = demo_script(dpath)

    pyexe = sys.executable

    self = BashJob(f'{pyexe} {script_fpath} --failflag --steps=4', 'myjob', log=True)
    self.rprint(1, 1)

    self = BashJob(f'{pyexe} {script_fpath}  --failflag --steps=4', 'myjob', log=False)
    self.rprint(1, 1)


def test_tmux_queue_errors():
    import ubelt as ub
    import sys
    import cmd_queue
    dpath = ub.Path.appdir('cmd_queue', 'tests', 'test_tmux_queue_errors')
    dpath.delete().ensuredir()
    script_fpath = demo_script(dpath)
    pyexe = sys.executable

    log = True

    queue = cmd_queue.Queue.create(backend='tmux')
    job1 = queue.submit(f'{pyexe} {script_fpath} --steps=3 --steptime=0.5', log=log)
    job2 = queue.submit(f'{pyexe} {script_fpath} --steps=2 --steptime=0.5 --failflag', log=log, depends=job1)
    job3 = queue.submit(f'{pyexe} {script_fpath} --steps=2 --steptime=0.5', log=log, depends=job2)
    job4 = queue.submit(f'{pyexe} {script_fpath} --steps=2 --steptime=0.5', log=log)
    # queue.submit(f'{pyexe} {script_fpath} --steps=2', log=log)
    queue.rprint(1, 1)
    queue.write()

    if not queue.is_available():
        import pytest
        pytest.skip('Skip tmux test. Tmux is not available')

    queue.run(block=0)
    queue.monitor(with_textual=False)
    queue.kill()

    assert 'Exception' in job2.log_fpath.read_text()
    assert 'Exception' not in job1.log_fpath.read_text()
    assert not job3.log_fpath.exists()
    assert 'Exception' not in job4.log_fpath.read_text()
