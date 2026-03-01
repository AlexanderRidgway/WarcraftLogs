import logging
from datetime import datetime
from sqlalchemy import select, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from web.api.models import Player, Score, Ranking, AttendanceRecord, ConsumablesData, GearSnapshot, Death, Fight, Badge

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
