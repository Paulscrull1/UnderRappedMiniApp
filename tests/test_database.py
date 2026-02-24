"""Тесты модуля database."""
import os
import pytest


def test_init_db(temp_db):
    import database
    conn = database._connect()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cursor.fetchall()}
    conn.close()
    assert "reviews" in tables
    assert "users" in tables
    assert "user_favorites" in tables
    assert "user_progress" in tables


def test_save_and_get_user_nickname(temp_db):
    import database
    database.save_user_nickname(1, "TestUser")
    assert database.get_user_nickname(1) == "TestUser"
    database.save_user_nickname(1, "NewNick")
    assert database.get_user_nickname(1) == "NewNick"


def test_save_review_and_get_last_reviews(temp_db):
    import database
    ratings = {"rhymes": 5, "rhythm": 6, "style": 7, "charisma": 8, "vibe": 9}
    database.save_review(1, "tid:1", ratings, "Track", "Artist", "User")
    reviews = database.get_last_reviews(1, limit=5)
    assert len(reviews) == 1
    assert reviews[0]["title"] == "Track"
    assert reviews[0]["artist"] == "Artist"
    assert reviews[0]["total"] == 35


def test_favorites(temp_db):
    import database
    database.add_favorite(1, "t1:a1", "Title", "Artist")
    assert database.is_in_favorites(1, "t1:a1") is True
    favs = database.get_favorites(1)
    assert len(favs) == 1
    assert favs[0]["track_id"] == "t1:a1"
    database.remove_favorite(1, "t1:a1")
    assert database.is_in_favorites(1, "t1:a1") is False


def test_user_progress(temp_db):
    import database
    database.add_exp(100, 50)
    database.add_exp(100, 30)
    p = database.get_user_progress(100)
    assert p["exp"] == 80
    assert p["level"] == 1 + 80 // 100  # 1


def test_get_top_tracks_by_rating(temp_db):
    import database
    r = {"rhymes": 10, "rhythm": 10, "style": 10, "charisma": 10, "vibe": 10}
    database.save_review(1, "t1", r, "A", "Art1", "U1")
    database.save_review(2, "t1", r, "A", "Art1", "U2")
    top = database.get_top_tracks_by_rating(limit=5)
    assert len(top) >= 1
    assert top[0]["track_id"] == "t1"
    assert top[0]["title"] == "A"
    assert top[0]["count"] == 2


def test_get_recent_reviews_with_text(temp_db):
    import database
    r = {"rhymes": 1, "rhythm": 1, "style": 1, "charisma": 1, "vibe": 1}
    database.save_review(1, "t1", r, "T", "A", "U", review_text="Cool track")
    recent = database.get_recent_reviews_with_text(limit=5)
    assert len(recent) == 1
    assert recent[0]["text"] == "Cool track"
