import datetime

import pytest
from pytest import Config as PytestConfig

from melt.flaky_test_db import (
    count_impacted_merge_requests,
    get_flaky_tests,
    log_flaky_test_run,
)

FLAKY_TEST_MAX_AGE = datetime.timedelta(days=1)
FLAKY_TEST_MAX_AGE_HOURS = FLAKY_TEST_MAX_AGE.total_seconds() / 3600
IMPACTED_MERGE_REQUEST_SKIP_THRESHOLD = 3


class MeltPlugin:
    def __init__(self):
        # Global variable since we need to conserve state between hook calls
        self.rerun_tests = set()
        # Store tests to check for markers later
        self.test_items = {}

    def pytest_runtest_logreport(self, report):
        if (
            # We don't care about setup/teardown
            report.when != "call"
            # We can't detect flaky tests when running without `--reruns`
            or not hasattr(report, "rerun")
            or (
                # If not - the test was added after our `modifyitems` hook - we'll compromise and
                # just say that it's not marked as flaky
                report.nodeid in self.test_items
                # The test is properly marked as flaky - no need to log it
                and self.test_items[report.nodeid].get_closest_marker("flaky")
            )
        ):
            return

        if report.rerun:
            self.rerun_tests.add(report.nodeid)
        elif report.passed and report.nodeid in self.rerun_tests:
            log_flaky_test_run(report.nodeid)

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items):
        flaky_tests = list(get_flaky_tests(FLAKY_TEST_MAX_AGE))
        node_id_to_test = {test.node_id: test for test in flaky_tests}

        for item in items:
            # `pytest_runtest_logreport` doesn't get items - we'll save them here for later
            self.test_items[item.nodeid] = item

            if item.nodeid in node_id_to_test:
                test = node_id_to_test[item.nodeid]
                impacted_merge_requests = count_impacted_merge_requests(
                    test, FLAKY_TEST_MAX_AGE
                )
                if impacted_merge_requests >= IMPACTED_MERGE_REQUEST_SKIP_THRESHOLD:
                    item.add_marker(
                        pytest.mark.skip(
                            f"Flaky - impacted {impacted_merge_requests} merge requests "
                            f"in the last {int(FLAKY_TEST_MAX_AGE_HOURS)} hours "
                            f"(last update: {test.last_updated.isoformat(sep=' ', timespec='minutes')})"
                        )
                    )


def pytest_configure(config: PytestConfig) -> None:
    if config.pluginmanager.has_plugin("rerunfailures"):
        config.pluginmanager.register(MeltPlugin(), "melt")
    else:
        print("Warning: melt requires pytest-rerunfailures to be installed.")
