import threading
import time
from collections import deque

from scripts.jurisdiction_expansion_full import (
    authorized_worker_cap,
    drain_continuous_queue,
)


def test_continuous_queue_replenishes_without_exceeding_worker_bound():
    lock = threading.Lock()
    active = 0
    maximum_active = 0
    completed = []

    def submit(item):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        # Unequal durations reproduce the condition that made wave scheduling
        # leave capacity idle while it waited for the slowest request.
        time.sleep(0.005 if item % 3 else 0.02)
        with lock:
            active -= 1
        return item

    def finish(item, result):
        completed.append(result)
        return None

    drain_continuous_queue(
        deque(range(20)),
        workers=4,
        can_submit=lambda inflight: True,
        submit_attempt=submit,
        finish_attempt=finish,
    )

    assert sorted(completed) == list(range(20))
    assert maximum_active == 4


def test_worker_cap_requires_authorized_amendment():
    manifest = {"maximum_workers": 4}
    assert authorized_worker_cap(manifest) == 4
    manifest["concurrency_amendment"] = {
        "user_authorized": False,
        "maximum_workers": 8,
    }
    assert authorized_worker_cap(manifest) == 4
    manifest["concurrency_amendment"]["user_authorized"] = True
    assert authorized_worker_cap(manifest) == 8
    manifest["concurrency_amendment"].update({
        "trial_outcome": "failed_provider_concurrency_limit",
        "effective_maximum_workers": 4,
    })
    assert authorized_worker_cap(manifest) == 4
