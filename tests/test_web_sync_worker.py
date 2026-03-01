def test_worker_importable():
    from web.api.sync.worker import SyncWorker
    assert SyncWorker is not None


def test_worker_has_required_methods():
    from web.api.sync.worker import SyncWorker
    assert hasattr(SyncWorker, "start")
    assert hasattr(SyncWorker, "stop")
    assert hasattr(SyncWorker, "run_roster_sync")
    assert hasattr(SyncWorker, "run_reports_sync")
