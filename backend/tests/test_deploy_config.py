"""Week 12: settings for hosting on Render."""
import threading

from app.core.config import Settings
from app.worker import start_in_background


def test_host_database_addresses_get_the_psycopg_driver():
    for given in ("postgres://u:p@host:5432/db", "postgresql://u:p@host:5432/db"):
        settings = Settings(database_url=given)
        assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_an_address_that_already_names_the_driver_is_kept():
    given = "postgresql+psycopg://u:p@host:5432/db"
    assert Settings(database_url=given).database_url == given


def test_the_worker_runs_in_the_api_only_when_asked():
    assert Settings(run_worker_in_api=False).run_worker_in_api is False
    assert Settings(run_worker_in_api="true").run_worker_in_api is True


def test_the_background_worker_stops_when_told(monkeypatch):
    started = threading.Event()

    def fake_loop(stopping):
        started.set()
        stopping.wait(5)

    monkeypatch.setattr("app.worker.run_loop", fake_loop)
    stop = start_in_background()

    assert started.wait(2)
    stop.set()
    worker = next(t for t in threading.enumerate() if t.name == "reminder-worker")
    worker.join(2)
    assert not worker.is_alive()
