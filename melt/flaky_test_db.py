import datetime
import os
from typing import Iterator

from peewee import (
    AutoField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

db = SqliteDatabase(":memory:")


class BaseModel(Model):
    class Meta:
        database = db


class FlakyTest(BaseModel):
    id_ = AutoField(column_name="id")
    node_id = TextField(unique=True)
    first_seen = DateTimeField(default=datetime.datetime.now, index=True)
    last_updated = DateTimeField(default=datetime.datetime.now, index=True)


class FlakyTestRun(BaseModel):
    id_ = AutoField(column_name="id")
    test = ForeignKeyField(FlakyTest)
    job_name = TextField(default=os.environ["CI_JOB_NAME"])
    job_id = IntegerField(default=int(os.environ["CI_JOB_ID"]))
    mr_id = IntegerField(default=int(os.environ["CI_MERGE_REQUEST_IID"]))
    pipeline_id = IntegerField(default=int(os.environ["CI_PIPELINE_IID"]))
    commit_hash = TextField(default=os.environ["CI_COMMIT_SHA"])
    timestamp = DateTimeField(default=datetime.datetime.now, index=True)

    class Meta:
        indexes = (
            # Create a unique index - there should only be one instance of a test
            # for each job.
            (("test", "job_id"), True),
        )


def get_flaky_tests(max_age: datetime.timedelta) -> Iterator[FlakyTest]:
    after = datetime.datetime.now() - max_age
    return FlakyTest.select().where(FlakyTest.last_updated >= after)


def log_flaky_test_run(nodeid: str) -> None:
    (
        # last_updated defaults to now
        FlakyTest.insert(node_id=nodeid)
        .on_conflict(
            # The test might already exist in the DB
            conflict_target=(FlakyTest.node_id,),
            # Only update last_updated, keeping the DB's first_seen
            preserve=(FlakyTest.last_updated,),
        )
        .execute()
    )

    test = FlakyTest.get(FlakyTest.node_id == nodeid)
    FlakyTestRun.create(test=test, commit_hash="fefef")


def count_impacted_merge_requests(test: FlakyTest, max_age: datetime.timedelta) -> int:
    after = datetime.datetime.now() - max_age
    return (
        FlakyTestRun.select()
        .where(FlakyTestRun.test == test and FlakyTestRun.timestamp >= after)
        .group_by(FlakyTestRun.mr_id)
        .count()
    )


db.create_tables((FlakyTest, FlakyTestRun))
