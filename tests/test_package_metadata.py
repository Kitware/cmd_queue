"""Package metadata guardrails moved out of the unit test suite.

Dependency metadata should be checked by build/install CI smoke tests, not by
parsing setup/requirements internals during normal pytest runs.
"""

import pytest


@pytest.mark.skip(reason='metadata checks belong in build/install CI smoke tests')
def test_package_metadata_checked_by_ci_smoke_test():
    pass
