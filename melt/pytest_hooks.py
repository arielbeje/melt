import datetime

import pytest
from pytest import Config as PytestConfig

from melt.flaky_test_db import get_flaky_tests, log_flaky_test_run

FLAKY_TEST_UPDATED_THRESHOLD = datetime.timedelta(days=1)


class MeltPlugin:
    def __init__(self):
        # Global variable since we need to conserve state between hook calls
        self.rerun_tests = set()
        # Store tests to check for markers later
        self.test_items = {}

    def pytest_runtest_logreport(self, report):
        # We don't care about setup/teardown
        if report.when != "call":
            return

        if not hasattr(report, "rerun"):
            # We can't detect flaky tests when running without `--reruns`
            return

        if self.test_items[report.nodeid].get_closest_marker("flaky"):
            # The test is properly marked as flaky - no need to log it
            return

        if report.rerun:
            self.rerun_tests.add(report.nodeid)

        # If the test passed, but had previous failures, it's flaky
        if report.passed and report.nodeid in self.rerun_tests:
            log_flaky_test_run(report.nodeid)

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items):
        flaky_node_ids = {
            test.node_id for test in get_flaky_tests(FLAKY_TEST_UPDATED_THRESHOLD)
        }

        for item in items:
            # `pytest_runtest_logreport` doesn't get items - we'll save them here for later
            self.test_items[item.nodeid] = item

            if item.nodeid in flaky_node_ids:
                # item.add_marker(pytest.mark.skip("Flaky"))
                pass


def pytest_configure(config: PytestConfig) -> None:
    if config.pluginmanager.has_plugin("rerunfailures"):
        config.pluginmanager.register(MeltPlugin(), "melt")
    else:
        print("Warning: melt requires pytest-rerunfailures to be installed.")
