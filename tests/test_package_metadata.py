"""Smoke tests for generated dependency metadata inputs.

These tests intentionally exercise the same ``parse_requirements`` helper used
by setup.py so strict/loose dependency regressions are caught before CI reaches
slow runtime tests.
"""

import importlib.util
from pathlib import Path


def _load_setup_module():
    repo_dpath = Path(__file__).resolve().parents[1]
    setup_fpath = repo_dpath / 'setup.py'
    spec = importlib.util.spec_from_file_location(
        'cmd_queue_setup_for_metadata_tests', setup_fpath
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_strict_tests_metadata_keeps_python311_off_coverage6():
    setup_mod = _load_setup_module()
    strict_tests = setup_mod.parse_requirements(
        'requirements/tests.txt', versions='strict'
    )

    assert (
        "coverage==7.0.0;python_version < '3.12' and python_version >= '3.11'"
        in strict_tests
    )
    assert (
        "coverage==6.1.1;python_version < '3.11' and python_version >= '3.10'"
        in strict_tests
    )
    assert (
        "coverage==6.1.1;python_version < '3.12' and python_version >= '3.10'"
        not in strict_tests
    )


def test_strict_optional_metadata_keeps_airflow_in_airflow_extra():
    setup_mod = _load_setup_module()
    strict_optional = setup_mod.parse_requirements(
        'requirements/optional.txt', versions='strict'
    )
    strict_airflow = setup_mod.parse_requirements(
        'requirements/airflow.txt', versions='strict'
    )

    assert any(req.startswith('apache-airflow==') for req in strict_airflow)
    assert set(strict_airflow).issubset(set(strict_optional))


def test_runtime_strict_metadata_has_expected_core_packages():
    setup_mod = _load_setup_module()
    strict_runtime = setup_mod.parse_requirements(
        'requirements/runtime.txt', versions='strict'
    )
    package_names = {req.split('==', 1)[0].split('>=', 1)[0].split(';', 1)[0] for req in strict_runtime}

    assert {'numpy', 'ubelt', 'kwutil', 'networkx', 'rich', 'scriptconfig'}.issubset(
        package_names
    )
