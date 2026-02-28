from datetime import datetime, timezone


def group_reports_by_week(reports: list) -> dict:
    """
    Group reports by ISO week.

    Returns dict of (year, week_number) -> list of reports.
    """
    weeks: dict[tuple[int, int], list] = {}
    for report in reports:
        dt = datetime.fromtimestamp(report["startTime"] / 1000, tz=timezone.utc)
        iso = dt.isocalendar()
        key = (iso[0], iso[1])  # (year, week)
        weeks.setdefault(key, []).append(report)
    return weeks


def check_player_attendance(
    player_name: str,
    reports: list,
    requirements: list,
) -> list:
    """
    Check a player's attendance against weekly requirements.

    Returns a list of week records sorted most recent first, each containing:
    - week_start: date string for the Monday of that week
    - attended: number of required zones the player attended
    - required: total number of required zone slots
    - zones: list of {zone_id, label, required, count, met}
    """
    weeks = group_reports_by_week(reports)
    result = []

    for (year, week_num), week_reports in sorted(weeks.items(), reverse=True):
        week_monday = datetime.fromisocalendar(year, week_num, 1)
        zone_results = []
        attended = 0

        for req in requirements:
            zone_id = req["zone_id"]
            required = req["required_per_week"]
            player_lower = player_name.lower()
            count = sum(
                1 for r in week_reports
                if r["zone"]["id"] == zone_id and player_lower in [p.lower() for p in r["players"]]
            )
            met = count >= required
            if met:
                attended += 1
            zone_results.append({
                "zone_id": zone_id,
                "label": req["label"],
                "required": required,
                "count": count,
                "met": met,
            })

        result.append({
            "week_start": week_monday.strftime("%b %d"),
            "attended": attended,
            "required": len(requirements),
            "zones": zone_results,
        })

    return result
