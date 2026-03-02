import logging
from datetime import datetime
from sqlalchemy import select, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.models import Player, Score, Ranking, AttendanceRecord, ConsumablesData, GearSnapshot, Death, Fight, Badge, Report

logger = logging.getLogger(__name__)

BADGE_DEFINITIONS = [
    {"type": "parse_god", "label": "Parse God", "description": "99+ parse on any boss"},
    {"type": "consistency_king", "label": "Consistency King", "description": "90+ overall score for 4+ consecutive raids"},
    {"type": "iron_raider", "label": "Iron Raider", "description": "100% attendance for 4+ consecutive weeks"},
    {"type": "flask_master", "label": "Flask Master", "description": "100% flask uptime for 4+ consecutive raids"},
    {"type": "most_improved", "label": "Most Improved", "description": "Biggest score increase over 4 weeks"},
    {"type": "deathless", "label": "Deathless", "description": "Zero deaths in a full raid clear"},
    {"type": "utility_star", "label": "Utility Star", "description": "95%+ utility score for 4+ consecutive raids"},
    {"type": "geared_up", "label": "Geared Up", "description": "All items epic+, fully enchanted and gemmed"},
]


async def evaluate_badges(session: AsyncSession):
    """Check all players against badge criteria and award new badges."""
    players_result = await session.execute(select(Player))
    players = players_result.scalars().all()

    for player in players:
        await _check_parse_god(session, player)
        await _check_consistency_king(session, player)
        await _check_iron_raider(session, player)
        await _check_utility_star(session, player)
        await _check_flask_master(session, player)
        await _check_deathless(session, player)
        await _check_geared_up(session, player)

    # Most improved: find the player with biggest score increase
    await _check_most_improved(session, players)

    await session.commit()
    logger.info("Badge evaluation complete")


async def _award_badge(session: AsyncSession, player_id: int, badge_type: str, details: str):
    """Award a badge if not already awarded (unique constraint prevents duplicates)."""
    existing = await session.execute(
        select(Badge).where(
            Badge.player_id == player_id,
            Badge.badge_type == badge_type,
            Badge.details == details,
        )
    )
    if existing.scalar_one_or_none():
        return
    session.add(Badge(player_id=player_id, badge_type=badge_type, details=details))


async def _check_parse_god(session: AsyncSession, player):
    """99+ parse on any boss."""
    result = await session.execute(
        select(Ranking)
        .where(Ranking.player_id == player.id, Ranking.rank_percent >= 99)
        .order_by(Ranking.recorded_at.desc())
        .limit(5)
    )
    for r in result.scalars().all():
        details = f"{r.rank_percent:.1f}% on {r.encounter_name}"
        await _award_badge(session, player.id, "parse_god", details)


async def _check_consistency_king(session: AsyncSession, player):
    """90+ overall score for 4+ consecutive raids."""
    result = await session.execute(
        select(Score)
        .where(Score.player_id == player.id)
        .order_by(Score.recorded_at.desc())
        .limit(10)
    )
    scores = result.scalars().all()
    consecutive = 0
    for s in scores:
        if s.overall_score >= 90:
            consecutive += 1
            if consecutive >= 4:
                await _award_badge(session, player.id, "consistency_king", f"{consecutive} consecutive raids at 90+")
                break
        else:
            break


async def _check_iron_raider(session: AsyncSession, player):
    """100% attendance for 4+ consecutive weeks."""
    result = await session.execute(
        select(
            AttendanceRecord.year,
            AttendanceRecord.week_number,
            func.min(AttendanceRecord.met.cast(Integer)).label("all_met"),
        )
        .where(AttendanceRecord.player_id == player.id)
        .group_by(AttendanceRecord.year, AttendanceRecord.week_number)
        .order_by(AttendanceRecord.year.desc(), AttendanceRecord.week_number.desc())
    )
    consecutive = 0
    for row in result.all():
        if row.all_met:
            consecutive += 1
            if consecutive >= 4:
                await _award_badge(session, player.id, "iron_raider", f"{consecutive} consecutive weeks perfect attendance")
                break
        else:
            break


async def _check_utility_star(session: AsyncSession, player):
    """95%+ utility score for 4+ consecutive raids."""
    result = await session.execute(
        select(Score)
        .where(Score.player_id == player.id, Score.utility_score.isnot(None))
        .order_by(Score.recorded_at.desc())
        .limit(10)
    )
    scores = result.scalars().all()
    consecutive = 0
    for s in scores:
        if s.utility_score is not None and s.utility_score >= 95:
            consecutive += 1
            if consecutive >= 4:
                await _award_badge(session, player.id, "utility_star", f"{consecutive} consecutive raids at 95%+ utility")
                break
        else:
            break


async def _check_most_improved(session: AsyncSession, players):
    """Award to the player with the biggest score increase over recent data."""
    best_improvement = 0
    best_player = None

    for player in players:
        result = await session.execute(
            select(Score)
            .where(Score.player_id == player.id)
            .order_by(Score.recorded_at.asc())
        )
        scores = result.scalars().all()
        if len(scores) < 4:
            continue
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        avg_first = sum(s.overall_score for s in first_half) / len(first_half)
        avg_second = sum(s.overall_score for s in second_half) / len(second_half)
        improvement = avg_second - avg_first
        if improvement > best_improvement:
            best_improvement = improvement
            best_player = player

    if best_player and best_improvement >= 5:
        await _award_badge(
            session, best_player.id, "most_improved",
            f"+{best_improvement:.1f} points improvement"
        )


async def _check_flask_master(session: AsyncSession, player):
    """100% flask uptime for 4+ consecutive raids."""
    result = await session.execute(
        select(ConsumablesData.report_code, ConsumablesData.actual_value)
        .join(Score, (Score.player_id == ConsumablesData.player_id) & (Score.report_code == ConsumablesData.report_code))
        .where(
            ConsumablesData.player_id == player.id,
            ConsumablesData.metric_name == "flask_uptime",
        )
        .order_by(Score.recorded_at.desc())
    )
    rows = result.all()
    consecutive = 0
    for row in rows:
        if row.actual_value >= 95:
            consecutive += 1
            if consecutive >= 4:
                await _award_badge(session, player.id, "flask_master", f"{consecutive} consecutive raids with flask")
                break
        else:
            break


async def _check_deathless(session: AsyncSession, player):
    """Zero deaths in a full raid clear (all fights are kills)."""
    # Find reports where this player has scores
    score_result = await session.execute(
        select(Score.report_code).where(Score.player_id == player.id)
    )
    report_codes = [r.report_code for r in score_result.all()]

    for report_code in report_codes:
        # Get all fights for this report
        fights_result = await session.execute(
            select(Fight).where(Fight.report_code == report_code)
        )
        fights = fights_result.scalars().all()
        if not fights:
            continue
        # All fights must be kills for a "full clear"
        if not all(f.kill for f in fights):
            continue
        # Check that the player has zero deaths across all fights
        fight_ids = [f.id for f in fights]
        death_count_result = await session.execute(
            select(func.count(Death.id)).where(
                Death.fight_db_id.in_(fight_ids),
                Death.player_id == player.id,
            )
        )
        death_count = death_count_result.scalar()
        if death_count == 0:
            # Get zone name from report
            report_result = await session.execute(
                select(Report.zone_name).where(Report.code == report_code)
            )
            zone_row = report_result.first()
            zone_name = zone_row.zone_name if zone_row else "Unknown"
            await _award_badge(session, player.id, "deathless", f"{zone_name} ({report_code})")


async def _check_geared_up(session: AsyncSession, player):
    """All items epic+, fully enchanted and gemmed."""
    # Enchantable slots (WoW slot IDs)
    enchant_slots = {0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15}

    # Get the latest report_code with gear for this player
    latest_result = await session.execute(
        select(GearSnapshot.report_code)
        .where(GearSnapshot.player_id == player.id)
        .order_by(GearSnapshot.recorded_at.desc())
        .limit(1)
    )
    latest_row = latest_result.first()
    if not latest_row:
        return

    report_code = latest_row.report_code
    gear_result = await session.execute(
        select(GearSnapshot).where(
            GearSnapshot.player_id == player.id,
            GearSnapshot.report_code == report_code,
        )
    )
    items = gear_result.scalars().all()
    if not items:
        return

    for item in items:
        # All items must be epic (quality >= 4)
        if item.quality < 4:
            return
        # Enchantable slots must have enchants
        if item.slot in enchant_slots and not item.permanent_enchant:
            return
        # All gem slots must be filled (non-empty gems list)
        if item.gems and any(g.get("id", 0) == 0 for g in item.gems):
            return

    await _award_badge(session, player.id, "geared_up", f"report {report_code}")
