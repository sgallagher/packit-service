# MIT License
#
# Copyright (c) 2018-2020 Red Hat, Inc.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
These tests require a psql database with a schema:
```
export POSTGRESQL_USER=packit
export POSTGRESQL_PASSWORD=secret-password
export POSTGRESQL_DATABASE=packit
export POSTGRESQL_SERVICE_HOST=0.0.0.0
$ docker-compose -d postgres
$ alembic upgrade head
```
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import ProgrammingError

from packit_service.models import (
    CoprBuild,
    get_sa_session,
    SRPMBuild,
    PullRequest,
    GitProject,
)

TARGET = "fedora-42-x86_64"


def clean_db():
    with get_sa_session() as session:
        session.query(CoprBuild).delete()
        session.query(PullRequest).delete()
        session.query(GitProject).delete()


@pytest.fixture()
def a_copr_build():
    with get_sa_session() as session:
        session.query(CoprBuild).delete()
        srpm_build = SRPMBuild.create("asd\nqwe\n")
        yield CoprBuild.get_or_create(
            pr_id=1,
            build_id="123456",
            commit_sha="687abc76d67d",
            repo_name="lithium",
            namespace="nirvana",
            web_url="https://copr.something.somewhere/123456",
            target=TARGET,
            status="pending",
            srpm_build=srpm_build,
        )
    clean_db()


def test_create_copr_build(a_copr_build):
    assert a_copr_build.pr_id == a_copr_build.pr.id
    assert a_copr_build.pr.pr_id == 1
    assert a_copr_build.build_id == "123456"
    assert a_copr_build.commit_sha == "687abc76d67d"
    assert a_copr_build.pr.project.namespace == "nirvana"
    assert a_copr_build.pr.project.repo_name == "lithium"
    assert a_copr_build.web_url == "https://copr.something.somewhere/123456"
    assert a_copr_build.srpm_build.logs == "asd\nqwe\n"
    assert a_copr_build.target == TARGET
    assert a_copr_build.status == "pending"
    # Since datetime.utcnow() will return different results in every time its called,
    # we will check if a_copr_build has build_submitted_time value thats within the past hour
    time_last_hour = datetime.utcnow() - timedelta(hours=1)
    assert a_copr_build.build_submitted_time > time_last_hour


def test_get_copr_build(a_copr_build):
    assert a_copr_build.id
    b = CoprBuild.get_by_build_id(a_copr_build.build_id, TARGET)
    assert b.id == a_copr_build.id
    # let's make sure passing int works as well
    b = CoprBuild.get_by_build_id(int(a_copr_build.build_id), TARGET)
    assert b.id == a_copr_build.id
    b2 = CoprBuild.get_by_id(b.id)
    assert b2.id == a_copr_build.id


def test_copr_build_set_status(a_copr_build):
    assert a_copr_build.status == "pending"
    a_copr_build.set_status("awesome")
    assert a_copr_build.status == "awesome"
    b = CoprBuild.get_by_build_id(a_copr_build.build_id, TARGET)
    assert b.status == "awesome"


def test_copr_build_set_build_logs_url(a_copr_build):
    url = "https://copr.fp.o/logs/12456/build.log"
    a_copr_build.set_build_logs_url(url)
    assert a_copr_build.build_logs_url == url
    b = CoprBuild.get_by_build_id(a_copr_build.build_id, TARGET)
    assert b.build_logs_url == url


def test_get_or_create_pr():
    clean_db()
    with get_sa_session() as session:
        try:
            expected_pr = PullRequest.get_or_create(
                pr_id=42, namespace="clapton", repo_name="layla"
            )
            actual_pr = PullRequest.get_or_create(
                pr_id=42, namespace="clapton", repo_name="layla"
            )

            assert session.query(PullRequest).count() == 1
            assert expected_pr.project_id == actual_pr.project_id

            expected_pr = PullRequest.get_or_create(
                pr_id=42, namespace="clapton", repo_name="cocaine"
            )
            actual_pr = PullRequest.get_or_create(
                pr_id=42, namespace="clapton", repo_name="cocaine"
            )

            assert session.query(PullRequest).count() == 2
            assert expected_pr.project_id == actual_pr.project_id
        finally:
            clean_db()


def test_errors_while_doing_db():
    with get_sa_session() as session:
        try:
            try:
                PullRequest.get_or_create(pr_id="nope", namespace="", repo_name=False)
            except ProgrammingError:
                pass
            assert len(session.query(PullRequest).all()) == 0
            PullRequest.get_or_create(pr_id=111, namespace="asd", repo_name="qwe")
            assert len(session.query(PullRequest).all()) == 1
        finally:
            clean_db()
