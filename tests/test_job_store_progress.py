"""Job store progress fields (monotonic updates for report polling UI)."""

from __future__ import annotations

import pytest

from backend.job_store import create_job_store, set_pending, set_progress, set_running


@pytest.fixture()
def store():
    return create_job_store()


def test_set_running_seeds_progress_and_stage(store):
    rid = "r1"
    set_pending(store, rid)
    set_running(store, rid)
    job = store["_jobs"][rid]
    assert job["status"] == "running"
    assert job["progress"] == 5
    assert "stage" in job


def test_set_progress_monotonic_increase_only(store):
    rid = "r2"
    set_pending(store, rid)
    set_running(store, rid)
    set_progress(store, rid, 30, "Mid")
    set_progress(store, rid, 20, "Lower")  # should not decrease
    job = store["_jobs"][rid]
    assert job["progress"] == 30
    assert job["stage"] == "Mid"


def test_set_progress_clamps_and_updates_stage_when_higher(store):
    rid = "r3"
    set_pending(store, rid)
    set_running(store, rid)
    set_progress(store, rid, 40, "A")
    set_progress(store, rid, 50, "B")
    job = store["_jobs"][rid]
    assert job["progress"] == 50
    assert job["stage"] == "B"


def test_set_progress_ignores_unknown_job(store):
    set_progress(store, "missing", 99, "x")  # no crash


def test_set_progress_clamps_to_0_100(store):
    rid = "r4"
    set_pending(store, rid)
    set_running(store, rid)
    set_progress(store, rid, -10)
    assert store["_jobs"][rid]["progress"] == 5  # monotonic: prev was 5 from set_running
    set_progress(store, rid, 200)
    assert store["_jobs"][rid]["progress"] == 100
