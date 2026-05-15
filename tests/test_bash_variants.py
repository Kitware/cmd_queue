"""
Tests for multiple variants of bash job text construction.
"""

import subprocess
import tempfile

import kwutil
import ubelt as ub

from cmd_queue.serial_queue import BashJob


def test_primary_bash_job_text_variants():
    """
    This is a restricted form of: test_bash_job_variants_syntax_grided
    that makes it easier to manually test common cases.
    """
    main_variants = kwutil.Yaml.coerce(
        """
        - __testname__: plain jane
          cwd: False
          depends: False
          preamble: False
          log: False
          with_status: False
          with_gaurds: False

        - __testname__: the works
          cwd: True
          depends: True
          preamble: True
          log: True
          with_status: True
          with_gaurds: True
        """
    )

    dep = BashJob('echo hi', name='job1')

    for variant in main_variants:
        job_kwargs = {}
        if variant['depends']:
            job_kwargs['depends'] = [dep]
        if variant['cwd']:
            job_kwargs['cwd'] = '/foo/bar'
        if variant['preamble']:
            job_kwargs['preamble'] = [
                'export SETUP_LINE1=1',
                'export SETUP_LINE2=2',
            ]

        # ub.udict.__and__ accepts an iterable of keys.
        finalize_kwargs = ub.udict(variant) & {'with_status', 'with_gaurds'}  # ty: ignore[unsupported-operator]

        command = 'echo hi'
        self = BashJob(command, name='job2', **job_kwargs)
        self.log = variant['log']

        text = self.finalize_text(**finalize_kwargs)
        print('###')
        print(f'variant = {ub.urepr(variant, nl=1)}')
        print('###')
        print(ub.highlight_code(text, 'bash'))
        print('###')

        if variant['__testname__'] == 'plain jane':
            assert text.strip() == command, (
                'When there is nothing special, we just return the command as given'
            )
        if variant['__testname__'] == 'the works':
            assert 'pushd "/foo/bar"' in text
            assert 'popd' in text
            assert 'CHDIR_OK' in text, (
                'cwd=True should define CHDIR_OK and guard popd'
            )
            assert 'if [[ "$CHDIR_OK" == "1" ]]' in text or 'CHDIR_OK' in text
            assert 'export SETUP_LINE1=1' in text
            assert 'export SETUP_LINE2=2' in text
            assert 'tee' in text


def test_bash_job_variants_syntax_grided():
    basis = kwutil.Yaml.coerce(
        """
        cwd: [True, False]
        depends: [True, False]
        preamble: [True, False]
        log: [True, False]
        with_status: [True, False]
        with_gaurds: [True, False]
        """
    )
    grid_variants = list(ub.named_product(**basis))

    dep = BashJob('echo hi', name='job1')

    for variant in grid_variants:
        job_kwargs = {}
        if variant['depends']:
            job_kwargs['depends'] = [dep]
        if variant['cwd']:
            job_kwargs['cwd'] = '/foo/bar'
        if variant['preamble']:
            job_kwargs['preamble'] = [
                'export SETUP_LINE1=1',
                'export SETUP_LINE2=2',
            ]

        # ub.udict.__and__ accepts an iterable of keys.
        finalize_kwargs = ub.udict(variant) & {'with_status', 'with_gaurds'}  # ty: ignore[unsupported-operator]

        self = BashJob('echo hi', name='job2', **job_kwargs)
        self.log = variant['log']

        text = self.finalize_text(**finalize_kwargs)
        print('###')
        print(f'variant = {ub.urepr(variant, nl=1)}')
        print('---')
        print(ub.highlight_code(text, 'bash'))
        print('---')

        # Check for correct bash structure
        proc = subprocess.run(
            ['bash', '-n'],
            input=text,
            text=True,
            capture_output=True,
        )
        if proc.returncode == 0:
            print('Parse check is ok')
        else:
            raise AssertionError(
                f'bash syntax error: \nSTDERR:\n{proc.stderr}\nSCRIPT:\n{text}'
            )

        # --- Plain-jane invariant: if nothing special, should equal command
        if not any(variant.values()):
            assert text.strip() == 'echo hi', (
                'When there is nothing special, we just return the command as given'
            )

        # --- Preamble should not be echoed if guards are on (i.e. set -x happens after preamble)
        if variant['preamble']:
            assert 'export SETUP_LINE1=1' in text
            assert 'export SETUP_LINE2=2' in text

            if variant['with_gaurds']:
                pre_idx = text.find('export SETUP_LINE1=1')
                x_idx = text.find('set -x')
                assert pre_idx != -1 and x_idx != -1 and pre_idx < x_idx, (
                    'dont enable echo before preamble'
                )

        # --- Logging behavior
        if variant['log']:
            # When log is enabled, we expect tee + pipefail boilerplate
            assert 'tee' in text, 'log=True should use tee'
            # Be strict if log_fpath is available on self; otherwise fall back to generic checks
            if hasattr(self, 'log_fpath'):
                assert str(self.log_fpath) in text, (
                    'log=True should reference log_fpath'
                )
            if variant['with_gaurds']:
                assert 'set -o pipefail' in text, (
                    'log=True should enable pipefail'
                )
                assert 'set +o pipefail' in text, (
                    'log=True should restore pipefail'
                )
        else:
            # When log is disabled, we should not see pipefail boilerplate
            assert 'set -o pipefail' not in text, (
                'log=False should not enable pipefail'
            )
            assert 'set +o pipefail' not in text, (
                'log=False should not restore pipefail'
            )
            # tee should not appear unless user command includes it (unlikely in these tests)
            # If you want to be strict:
            assert 'tee ' not in text, 'log=False should not insert tee'

        # --- Guard behavior: when with_gaurds is enabled, we expect set +e and the brace return-code capture
        if variant['with_gaurds']:
            assert 'set +e' in text, (
                'with_gaurds=True should disable exit-on-error'
            )
            # We should enable xtrace somewhere (unless bookkeeper disables it; in your tests it should not)
            assert 'set -x' in text, (
                'with_gaurds=True should enable command echo'
            )
            # Return code capture should be hidden inside brace trick
            assert '{ RETURN_CODE=$?' in text, (
                'with_gaurds=True should capture RETURN_CODE in brace trick'
            )
            assert 'set +x -e' in text, (
                'with_gaurds=True should disable echo and re-enable -e'
            )
            # Ensure we don't have a noisy RETURN_CODE=$? line outside the brace trick
            bad_lines = [
                ln
                for ln in text.splitlines()
                if ln.strip().startswith('RETURN_CODE=$?')
            ]
            assert not bad_lines, (
                f'RETURN_CODE capture should be in brace trick, found: {bad_lines}'
            )
        else:
            # If guards are off, we should not see xtrace toggles or the brace trick capture
            assert 'set -x' not in text, (
                'with_gaurds=False should not enable xtrace'
            )
            assert 'set +x -e' not in text, (
                'with_gaurds=False should not include brace trick toggles'
            )
            assert '{ RETURN_CODE=$?' not in text, (
                'with_gaurds=False should not include brace trick capture'
            )

        # --- Status behavior
        if variant['with_status']:
            assert 'Mark job as running' in text, (
                'with_status=True should mark job as running'
            )
            assert 'Mark job as stopped' in text, (
                'with_status=True should mark job as stopped'
            )
            assert 'printf "pass" >' in text, (
                'with_status=True should write pass marker'
            )
            assert 'printf "fail" >' in text, (
                'with_status=True should write fail marker'
            )
            assert 'stat' in text or 'status' in text, (
                'with_status=True should dump status JSON'
            )
            # Make sure RETURN_CODE is referenced in final status conditional
            assert '"$RETURN_CODE"' in text or 'RETURN_CODE' in text, (
                'with_status=True should reference RETURN_CODE'
            )
        else:
            # When status is off, we should not emit pass/fail markers
            assert 'printf "pass" >' not in text, (
                'with_status=False should not write pass marker'
            )
            assert 'printf "fail" >' not in text, (
                'with_status=False should not write fail marker'
            )
            assert 'Mark job as running' not in text
            assert 'Mark job as stopped' not in text

        # --- Dependency guard behavior is only emitted when status is on and depends exist
        if variant['depends'] and variant['with_status']:
            assert 'if [ -f' in text, (
                'depends+with_status should emit dependency condition'
            )
            assert 'RETURN_CODE=126' in text, (
                'depends+with_status should set skip RETURN_CODE=126'
            )
        else:
            # Be careful: user command might contain this string, but in these tests it won't.
            assert 'RETURN_CODE=126' not in text, (
                'no depends or no status: should not insert skip RETURN_CODE'
            )

        # --- CWD behavior
        if variant['cwd']:
            assert 'pushd' in text, 'cwd=True should use pushd'
            assert 'popd' in text, 'cwd=True should include popd'
        else:
            assert 'pushd' not in text, 'cwd=False should not include pushd'
            assert 'popd' not in text, 'cwd=False should not include popd'

        # --- If we emit internal conditional checks (preamble/cwd), they must be closed properly
        if variant['cwd'] or variant['preamble']:
            # If you use a recognizable comment/tag, assert it exists
            if 'internal condition check' in text:
                assert 'fi  # internal condition check' in text, (
                    'internal if must be closed'
                )
            else:
                # Generic safety: at least ensure the count of 'if [[ ' and 'fi' isn't wildly off
                # (This is loose on purpose to avoid false positives with outer dependency if.)
                assert text.count('if [[ ') <= text.count('fi'), (
                    'seems like an internal if may be missing a fi'
                )

        # --- Optional: ordering sanity when guards+status on
        # Ensure xtrace starts after "Mark job as running" and stops before "Mark job as stopped"
        if variant['with_gaurds'] and variant['with_status']:
            running_idx = text.find('Mark job as running')
            x_idx = text.find('set -x')
            stopped_idx = text.find('Mark job as stopped')
            if running_idx != -1 and x_idx != -1 and stopped_idx != -1:
                assert running_idx < x_idx < stopped_idx, (
                    'xtrace should not include boilerplate status dump; it should wrap the payload'
                )

    n_checks = len(grid_variants)
    print(f'Ran all n_checks={n_checks}')


def test_bashjob_exec_preamble_fail():
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = ub.Path(tmp_path)
        workdir = tmp_path / 'work'
        workdir.mkdir()

        # Command would create a file if it ran — use that to detect it was skipped
        outfile = tmp_path / 'ran.txt'
        job = BashJob(f'echo ran > "{outfile}"', name='job2', cwd=str(workdir))
        job.preamble = ['false']  # fail-fast preamble
        job.log = False

        job.stat_fpath = tmp_path / 'job2.status.json'
        job.pass_fpath = tmp_path / 'job2.pass'
        job.fail_fpath = tmp_path / 'job2.fail'

        text = job.finalize_text(with_status=True, with_gaurds=True)
        subprocess.run(['bash', '-n'], input=text, text=True, check=True)

        subprocess.run(
            ['bash'],
            input=text,
            text=True,
            cwd=str(tmp_path),
            capture_output=True,
        )

        assert job.fail_fpath.exists()
        assert not outfile.exists(), 'command should not run if preamble fails'

        status = kwutil.Json.load(job.stat_fpath)
        assert status['ret'] != 0


def test_bashjob_exec_depends_met_runs():
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = ub.Path(tmp_path)
        workdir = tmp_path / 'work'
        workdir.mkdir()

        dep = BashJob('echo dep', name='dep_job')
        dep.pass_fpath = tmp_path / 'dep_job.pass'
        dep.fail_fpath = tmp_path / 'dep_job.fail'
        dep.stat_fpath = tmp_path / 'dep_job.status.json'

        # Create dependency pass marker
        dep.pass_fpath.parent.mkdir(parents=True, exist_ok=True)
        dep.pass_fpath.write_text('pass')

        outfile = tmp_path / 'ran.txt'
        job = BashJob(
            f'echo ran > "{outfile}"',
            name='job2',
            cwd=str(workdir),
            depends=[dep],
        )
        job.preamble = ['export SETUP_LINE1=1']
        job.log = False

        job.stat_fpath = tmp_path / 'job2.status.json'
        job.pass_fpath = tmp_path / 'job2.pass'
        job.fail_fpath = tmp_path / 'job2.fail'

        text = job.finalize_text(with_status=True, with_gaurds=True)
        subprocess.run(['bash', '-n'], input=text, text=True, check=True)

        subprocess.run(
            ['bash'],
            input=text,
            text=True,
            cwd=str(tmp_path),
            capture_output=True,
            check=False,
        )

        assert outfile.exists(), 'command should run if dependency is met'
        assert job.pass_fpath.exists(), 'job should pass'
        assert not job.fail_fpath.exists()

        status = kwutil.Json.load(job.stat_fpath)
        assert status['ret'] == 0


def test_bashjob_exec_depends_unmet_skips():
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = ub.Path(tmp_path)
        workdir = tmp_path / 'work'
        workdir.mkdir()

        dep = BashJob('echo dep', name='dep_job')
        dep.pass_fpath = tmp_path / 'dep_job.pass'
        dep.fail_fpath = tmp_path / 'dep_job.fail'
        dep.stat_fpath = tmp_path / 'dep_job.status.json'

        # Do NOT create dep.pass_fpath => dependency unmet

        outfile = tmp_path / 'ran.txt'
        job = BashJob(
            f'echo ran > "{outfile}"',
            name='job2',
            cwd=str(workdir),
            depends=[dep],
        )
        job.preamble = ['export SETUP_LINE1=1']
        job.log = False

        job.stat_fpath = tmp_path / 'job2.status.json'
        job.pass_fpath = tmp_path / 'job2.pass'
        job.fail_fpath = tmp_path / 'job2.fail'
        job.skip_fpath = tmp_path / 'job2.skip'

        text = job.finalize_text(with_status=True, with_gaurds=True)
        subprocess.run(['bash', '-n'], input=text, text=True, check=True)

        subprocess.run(
            ['bash'],
            input=text,
            text=True,
            cwd=str(tmp_path),
            capture_output=True,
            check=False,
        )

        assert not outfile.exists(), (
            'command should not run if dependency is unmet'
        )
        # Skipped jobs (deps unmet, RC=126) write skip_fpath only — they
        # are NOT also marked as failed.
        assert job.skip_fpath.exists(), 'skipped job should be marked as skip'
        assert not job.fail_fpath.exists(), (
            'skipped job should not be marked as fail'
        )
        assert not job.pass_fpath.exists()

        status = kwutil.Json.load(job.stat_fpath)
        assert status['ret'] == 126


def test_bashjob_exec_cwd_missing_skips_command():
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = ub.Path(tmp_path)

        missing_dir = tmp_path / 'does_not_exist'
        assert not missing_dir.exists()

        outfile = tmp_path / 'ran.txt'
        job = BashJob(
            f'echo ran > "{outfile}"', name='job2', cwd=str(missing_dir)
        )
        job.preamble = ['export SETUP_LINE1=1']
        job.log = False

        job.stat_fpath = tmp_path / 'job2.status.json'
        job.pass_fpath = tmp_path / 'job2.pass'
        job.fail_fpath = tmp_path / 'job2.fail'

        text = job.finalize_text(with_status=True, with_gaurds=True)
        subprocess.run(['bash', '-n'], input=text, text=True, check=True)

        subprocess.run(
            ['bash'],
            input=text,
            text=True,
            cwd=str(tmp_path),
            capture_output=True,
            check=False,
        )

        assert job.fail_fpath.exists(), 'missing cwd should mark job as failed'
        assert not outfile.exists(), 'command should not run if cwd pushd fails'
        assert not job.pass_fpath.exists()

        status = kwutil.Json.load(job.stat_fpath)
        assert status['ret'] != 0


def test_bashjob_exec_happy_path():
    with tempfile.TemporaryDirectory() as tmp_path:
        tmp_path = ub.Path(tmp_path)
        workdir = tmp_path / 'work'
        workdir.mkdir()

        outfile = tmp_path / 'ran.txt'
        job = BashJob(f'echo ran > "{outfile}"', name='job2', cwd=str(workdir))
        job.preamble = ['export SETUP_LINE1=1', 'export SETUP_LINE2=2']
        job.log = False

        job.stat_fpath = tmp_path / 'job2.status.json'
        job.pass_fpath = tmp_path / 'job2.pass'
        job.fail_fpath = tmp_path / 'job2.fail'

        text = job.finalize_text(with_status=True, with_gaurds=True)
        subprocess.run(['bash', '-n'], input=text, text=True, check=True)

        subprocess.run(
            ['bash'],
            input=text,
            text=True,
            cwd=str(tmp_path),
            capture_output=True,
            check=False,
        )

        assert outfile.exists(), 'command should run on happy path'
        assert job.pass_fpath.exists(), 'pass marker should exist'
        assert not job.fail_fpath.exists(), 'fail marker should not exist'

        status = kwutil.Json.load(job.stat_fpath)
        assert status['ret'] == 0
