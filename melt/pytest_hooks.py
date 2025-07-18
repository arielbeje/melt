import datetime

import pytest

from melt.flaky_test_db import get_flaky_tests, log_flaky_test_run

FLAKY_TEST_UPDATED_THRESHOLD = datetime.timedelta(days=1)


# Global variable since we need to conserve state between hook calls
rerun_tests = set()


def pytest_runtest_logreport(report):
    # We don't care about setup/teardown
    if report.when != "call":
        return

    if not hasattr(report, "rerun"):
        # We can't detect flaky tests when running without `--reruns`
        return

    if report.rerun:
        rerun_tests.add(report.nodeid)

    # If the test passed, but had previous failures, it's flaky
    if report.passed and report.nodeid in rerun_tests:
        log_flaky_test_run(report.nodeid)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items):
    flaky_node_ids = {
        test.node_id for test in get_flaky_tests(FLAKY_TEST_UPDATED_THRESHOLD)
    }

    for item in items:
        if item.nodeid in flaky_node_ids:
            # item.add_marker(pytest.mark.skip("Flaky"))
            pass
