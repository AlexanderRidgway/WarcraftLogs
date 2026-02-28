import sys
from unittest.mock import MagicMock

# Mock modules that have heavy/unavailable dependencies (discord, bot, etc.)
# so we can import just the _week_range_ms helper without side effects.
for mod_name in [
    "discord",
    "discord.app_commands",
    "discord.ext",
    "discord.ext.commands",
    "src.bot",
    "src.attendance",
    "src.attendance.checker",
    "src.gear",
    "src.gear.checker",
]:
    sys.modules.setdefault(mod_name, MagicMock())

import pytest
from datetime import datetime, timezone
from src.commands.weeklyrecap import _week_range_ms


def test_week_range_returns_monday_to_sunday():
    start_ms, end_ms, label = _week_range_ms(0)
    start_dt = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc)
    # Start should be a Monday
    assert start_dt.weekday() == 0
    # End should be a Sunday
    assert end_dt.weekday() == 6
    # Start should be midnight
    assert start_dt.hour == 0 and start_dt.minute == 0
    # End should be 23:59:59
    assert end_dt.hour == 23 and end_dt.minute == 59


def test_week_range_weeks_ago_goes_back():
    current_start, _, _ = _week_range_ms(0)
    prev_start, _, _ = _week_range_ms(1)
    # Previous week start should be exactly 7 days before current
    diff_days = (current_start - prev_start) / (1000 * 60 * 60 * 24)
    assert diff_days == pytest.approx(7.0, abs=0.01)


def test_week_range_label_format():
    _, _, label = _week_range_ms(0)
    # Label should be "Mon DD" format (e.g. "Feb 23")
    assert len(label.split()) == 2
