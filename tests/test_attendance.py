import pytest
from datetime import datetime, timezone
from src.attendance.checker import group_reports_by_week, check_player_attendance


def _ms(year, month, day):
    """Helper: return epoch milliseconds for a date at midnight UTC."""
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


SAMPLE_REQUIREMENTS = [
    {"zone_id": 1002, "label": "Karazhan", "required_per_week": 1},
    {"zone_id": 1004, "label": "Gruul's Lair", "required_per_week": 1},
    {"zone_id": 1005, "label": "Magtheridon's Lair", "required_per_week": 1},
]


def test_group_reports_by_week():
    # Feb 17 2026 is a Tuesday, Feb 24 2026 is a Tuesday
    # ISO week: Feb 16 (Mon) - Feb 22 (Sun) = week 8
    # ISO week: Feb 23 (Mon) - Mar 1 (Sun) = week 9
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
        {"code": "b", "startTime": _ms(2026, 2, 18), "zone": {"id": 1004, "name": "Gruul's Lair"}, "players": ["Thrallbro"]},
        {"code": "c", "startTime": _ms(2026, 2, 24), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro", "Healbot"]},
    ]
    grouped = group_reports_by_week(reports)
    # Should have 2 weeks
    assert len(grouped) == 2


def test_check_player_attendance_perfect():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
        {"code": "b", "startTime": _ms(2026, 2, 18), "zone": {"id": 1004, "name": "Gruul's Lair"}, "players": ["Thrallbro"]},
        {"code": "c", "startTime": _ms(2026, 2, 19), "zone": {"id": 1005, "name": "Magtheridon's Lair"}, "players": ["Thrallbro"]},
    ]
    result = check_player_attendance("Thrallbro", reports, SAMPLE_REQUIREMENTS)
    # One week, all 3 raids attended
    assert len(result) == 1
    week = result[0]
    assert week["attended"] == 3
    assert week["required"] == 3
    assert all(z["met"] for z in week["zones"])


def test_check_player_attendance_missed_one():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
        {"code": "b", "startTime": _ms(2026, 2, 18), "zone": {"id": 1004, "name": "Gruul's Lair"}, "players": ["Thrallbro"]},
        # No Magtheridon's
    ]
    result = check_player_attendance("Thrallbro", reports, SAMPLE_REQUIREMENTS)
    assert len(result) == 1
    week = result[0]
    assert week["attended"] == 2
    assert week["required"] == 3
    mag = next(z for z in week["zones"] if z["zone_id"] == 1005)
    assert mag["met"] is False


def test_check_player_attendance_not_in_any_report():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Healbot"]},
    ]
    result = check_player_attendance("Thrallbro", reports, SAMPLE_REQUIREMENTS)
    assert len(result) == 1
    assert result[0]["attended"] == 0


def test_check_player_attendance_multiple_reports_same_zone_same_week():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
        {"code": "b", "startTime": _ms(2026, 2, 19), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
    ]
    reqs = [{"zone_id": 1002, "label": "Karazhan", "required_per_week": 2}]
    result = check_player_attendance("Thrallbro", reports, reqs)
    assert len(result) == 1
    kara = result[0]["zones"][0]
    assert kara["met"] is True
    assert kara["count"] == 2


def test_check_player_attendance_required_2_only_did_1():
    reports = [
        {"code": "a", "startTime": _ms(2026, 2, 17), "zone": {"id": 1002, "name": "Karazhan"}, "players": ["Thrallbro"]},
    ]
    reqs = [{"zone_id": 1002, "label": "Karazhan", "required_per_week": 2}]
    result = check_player_attendance("Thrallbro", reports, reqs)
    kara = result[0]["zones"][0]
    assert kara["met"] is False
    assert kara["count"] == 1


def test_group_reports_empty():
    assert group_reports_by_week([]) == {}
