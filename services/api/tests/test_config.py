import pytest

from app.config import Settings


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('["https://a.vercel.app"]', ["https://a.vercel.app"]),
        ('["https://a.vercel.app","http://localhost:5173"]', ["https://a.vercel.app", "http://localhost:5173"]),
        ("https://a.vercel.app", ["https://a.vercel.app"]),
        ("https://a.vercel.app,http://localhost:5173", ["https://a.vercel.app", "http://localhost:5173"]),
        ("['https://a.vercel.app', 'http://localhost:5173']", ["https://a.vercel.app", "http://localhost:5173"]),
    ],
)
def test_cors_origins_accepts_json_and_csv(monkeypatch, raw, expected):
    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert Settings().cors_origins == expected


def test_cors_origins_defaults_when_empty(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "")
    assert Settings().cors_origins == []
