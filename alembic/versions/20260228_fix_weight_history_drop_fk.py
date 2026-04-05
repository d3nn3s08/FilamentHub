"""Fix weight_history FK mismatch: remove foreign key constraint on spool_uuid

Revision ID: 20260228_fix_weight_history_drop_fk
Revises: 20260221_fix_weight_history_fk_mismatch
Create Date: 2026-02-28

Problem: weight_history.spool_uuid hatte einen FK auf spool.tray_uuid,
aber spool.tray_uuid ist KEIN Primary Key und hat keinen UNIQUE Constraint.
SQLite wirft deshalb bei PRAGMA foreign_keys=ON einen 'foreign key mismatch'-Fehler
bei jedem INSERT in weight_history.

Loesung: Tabelle neu erstellen OHNE den FK-Constraint.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "20260228_fix_weight_history_drop_fk"
down_revision = "20260221_fix_weight_history_fk_mismatch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Entfernt den ungültigen Foreign Key von weight_history.spool_uuid.
    SQLite unterstützt kein ALTER TABLE DROP CONSTRAINT, daher wird
    die Tabelle neu erstellt.
    """
    bind = op.get_bind()

    print(">> Fixe weight_history FK mismatch...")

    # Prüfe ob Tabelle existiert
    table_row = bind.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='weight_history'")
    ).fetchone()

    if table_row is None:
        # Tabelle existiert nicht – neu erstellen ohne FK
        print("  >> Tabelle weight_history nicht gefunden, erstelle neu...")
        op.create_table(
            "weight_history",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("spool_uuid", sa.String(36), nullable=False),
            sa.Column("spool_number", sa.Integer(), nullable=True),
            sa.Column("old_weight", sa.Float(), nullable=False),
            sa.Column("new_weight", sa.Float(), nullable=False),
            sa.Column("source", sa.String(50), nullable=False),
            sa.Column("change_reason", sa.String(100), nullable=False),
            sa.Column("ams_type", sa.String(20), nullable=True),
            sa.Column("user", sa.String(100), nullable=False),
            sa.Column("timestamp", sa.DateTime(), nullable=False,
                      server_default=sa.func.current_timestamp()),
            sa.Column("details", sa.String(500), nullable=True),
        )
        print("  [OK] Tabelle weight_history erstellt (ohne FK)")
        return

    # Prüfe ob FK-Constraint vorhanden ist
    ddl_row = bind.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='weight_history'")
    ).fetchone()
    ddl_sql = ddl_row[0] if ddl_row and ddl_row[0] else ""

    if "REFERENCES" not in ddl_sql and "FOREIGN KEY" not in ddl_sql:
        print("  >> Kein FK-Constraint in weight_history – Migration nicht nötig")
        return

    print("  >> FK-Constraint gefunden, recreate weight_history ohne FK...")

    # Bestehende Daten sichern
    rows = bind.execute(
        text(
            "SELECT id, spool_uuid, spool_number, old_weight, new_weight, "
            "source, change_reason, ams_type, user, timestamp, details "
            "FROM weight_history"
        )
    ).fetchall()
    print(f"  >> {len(rows)} bestehende Zeilen gesichert")

    # Views entfernen (hängen von weight_history ab)
    bind.execute(text("DROP VIEW IF EXISTS v_active_spools_with_last_change"))
    bind.execute(text("DROP VIEW IF EXISTS v_archived_spools_by_number"))

    # Indizes entfernen
    for idx in [
        "ix_weight_history_spool_uuid",
        "idx_weight_history_spool_uuid",
        "idx_weight_history_timestamp",
        "idx_weight_history_source",
        "idx_weight_history_spool_timestamp",
    ]:
        bind.execute(text(f"DROP INDEX IF EXISTS {idx}"))

    # Neue Tabelle ohne FK erstellen
    bind.execute(text(
        "CREATE TABLE weight_history_new ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  spool_uuid VARCHAR(36) NOT NULL,"
        "  spool_number INTEGER,"
        "  old_weight FLOAT NOT NULL,"
        "  new_weight FLOAT NOT NULL,"
        "  source VARCHAR(50) NOT NULL,"
        "  change_reason VARCHAR(100) NOT NULL,"
        "  ams_type VARCHAR(20),"
        "  user VARCHAR(100) NOT NULL,"
        "  timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        "  details VARCHAR(500)"
        ")"
    ))

    # Daten übertragen
    if rows:
        for row in rows:
            bind.execute(
                text(
                    "INSERT INTO weight_history_new "
                    "(id, spool_uuid, spool_number, old_weight, new_weight, "
                    " source, change_reason, ams_type, user, timestamp, details) "
                    "VALUES (:id, :spool_uuid, :spool_number, :old_weight, :new_weight, "
                    "        :source, :change_reason, :ams_type, :user, :timestamp, :details)"
                ),
                {
                    "id": row[0],
                    "spool_uuid": row[1],
                    "spool_number": row[2],
                    "old_weight": row[3],
                    "new_weight": row[4],
                    "source": row[5],
                    "change_reason": row[6],
                    "ams_type": row[7],
                    "user": row[8],
                    "timestamp": row[9],
                    "details": row[10],
                },
            )

    # Alte Tabelle löschen, neue umbenennen
    bind.execute(text("DROP TABLE weight_history"))
    bind.execute(text("ALTER TABLE weight_history_new RENAME TO weight_history"))

    # Indizes neu erstellen
    bind.execute(text(
        "CREATE INDEX idx_weight_history_spool_uuid ON weight_history (spool_uuid)"
    ))
    bind.execute(text(
        "CREATE INDEX idx_weight_history_timestamp ON weight_history (timestamp)"
    ))
    bind.execute(text(
        "CREATE INDEX idx_weight_history_source ON weight_history (source)"
    ))
    bind.execute(text(
        "CREATE INDEX idx_weight_history_spool_timestamp "
        "ON weight_history (spool_uuid, timestamp)"
    ))

    # Views wiederherstellen
    bind.execute(text(
        "CREATE VIEW IF NOT EXISTS v_active_spools_with_last_change AS "
        "SELECT s.*, h.timestamp as last_change_timestamp, "
        "h.source as last_change_source, h.change_reason as last_change_reason "
        "FROM spool s "
        "LEFT JOIN ("
        "  SELECT spool_uuid, MAX(timestamp) as max_timestamp "
        "  FROM weight_history GROUP BY spool_uuid"
        ") h_max ON s.tray_uuid = h_max.spool_uuid "
        "LEFT JOIN weight_history h "
        "  ON h.spool_uuid = s.tray_uuid AND h.timestamp = h_max.max_timestamp "
        "WHERE s.is_active = 1"
    ))
    bind.execute(text(
        "CREATE VIEW IF NOT EXISTS v_archived_spools_by_number AS "
        "SELECT s.tray_uuid, s.last_number, s.color, s.vendor, s.emptied_at, "
        "COUNT(h.id) as total_changes "
        "FROM spool s "
        "LEFT JOIN weight_history h ON h.spool_uuid = s.tray_uuid "
        "WHERE s.is_active = 0 AND s.last_number IS NOT NULL "
        "GROUP BY s.tray_uuid, s.last_number, s.color, s.vendor, s.emptied_at "
        "ORDER BY s.last_number, s.emptied_at DESC"
    ))

    print(f"  [OK] weight_history FK-Constraint entfernt! ({len(rows)} Zeilen migriert)")


def downgrade() -> None:
    """Downgrade nicht implementiert (FK war fehlerhaft)."""
    pass
