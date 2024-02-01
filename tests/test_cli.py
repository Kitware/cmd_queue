
def test_cli():
    """
    Ensure the CLI works as expected
    """

    import ubelt as ub
    dpath = ub.Path.appdir('cmd_queue/tests/tests_cli').ensuredir()

    bash_text = ub.codeblock(
        r'''
        cmd_queue new testqueue1

        cmd_queue submit --jobname "job1" -- testqueue1 \
            python -c "print('hello world 1')"

        cmd_queue submit --jobname "job2" -- testqueue1 \
            python -c "print('hello world 2')"

        cmd_queue show testqueue1

        cmd_queue run testqueue1 --backend=serial
        ''')

    fpath = dpath / 'test_script.sh'
    fpath.write_text(bash_text)

    info = ub.cmd('bash test_script.sh', cwd=dpath, verbose=3)
    info.check_returncode()


def test_cli_single_executable():
    """
    Test just the submit and show part of the bash workflow
    """

    import ubelt as ub
    dpath = ub.Path.appdir('cmd_queue/tests/tests_cli').ensuredir()

    true_exe = ub.find_exe('true')

    bash_text = ub.codeblock(
        fr'''
        cmd_queue new testqueue2

        cmd_queue submit --jobname "job1" -- testqueue2 \
            true

        cmd_queue submit --jobname "job2" -- testqueue2 \
            {true_exe}

        cmd_queue show testqueue2

        cmd_queue run testqueue2 --backend=serial
        ''')

    fpath = dpath / 'test_script.sh'
    fpath.write_text(bash_text)

    info = ub.cmd('bash test_script.sh', cwd=dpath, verbose=3)
    info.check_returncode()
