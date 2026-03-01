def test_models_importable():
    from web.api.models import Base, Player, Report, Ranking, Score
    from web.api.models import GearSnapshot, UtilityData, ConsumablesData
    from web.api.models import AttendanceRecord, SyncStatus, User
    assert len(Base.metadata.tables) == 10


def test_player_table_columns():
    from web.api.models import Player
    columns = {c.name for c in Player.__table__.columns}
    assert columns == {"id", "name", "class_id", "class_name", "server", "region", "last_synced_at"}
