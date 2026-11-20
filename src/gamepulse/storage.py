from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import LevelEvent, PlayerProfile, RevenueEvent, SessionEvent


class AnalyticsStore:
    """Indexed SQLite analytical warehouse for player cohorts, sessions, monetization, and funnels."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                player_id TEXT PRIMARY KEY,
                install_date TEXT NOT NULL,
                channel TEXT NOT NULL,
                country TEXT NOT NULL,
                experiment_group TEXT NOT NULL,
                cpi_usd REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS sessions (
                event_id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                session_date TEXT NOT NULL,
                duration_sec INTEGER NOT NULL,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            );

            CREATE TABLE IF NOT EXISTS revenue_events (
                event_id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                event_date TEXT NOT NULL,
                source TEXT NOT NULL,
                amount_usd REAL NOT NULL,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            );

            CREATE TABLE IF NOT EXISTS level_events (
                event_id TEXT PRIMARY KEY,
                player_id TEXT NOT NULL,
                step_name TEXT NOT NULL,
                step_order INTEGER NOT NULL,
                event_date TEXT NOT NULL,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            );

            CREATE INDEX IF NOT EXISTS idx_players_install ON players(install_date, channel);
            CREATE INDEX IF NOT EXISTS idx_sessions_player_date ON sessions(player_id, session_date);
            CREATE INDEX IF NOT EXISTS idx_revenue_player ON revenue_events(player_id, event_date);
            CREATE INDEX IF NOT EXISTS idx_level_step ON level_events(step_order, player_id);
            """
        )
        self._conn.commit()

    def insert_players(self, players: Iterable[PlayerProfile]) -> None:
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO players
            (player_id, install_date, channel, country, experiment_group, cpi_usd)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (p.player_id, p.install_date, p.channel, p.country, p.experiment_group, p.cpi_usd)
                for p in players
            ],
        )
        self._conn.commit()

    def insert_sessions(self, sessions: Iterable[SessionEvent]) -> None:
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO sessions (event_id, player_id, session_date, duration_sec)
            VALUES (?, ?, ?, ?)
            """,
            [(s.event_id, s.player_id, s.session_date, s.duration_sec) for s in sessions],
        )
        self._conn.commit()

    def insert_revenue(self, events: Iterable[RevenueEvent]) -> None:
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO revenue_events (event_id, player_id, event_date, source, amount_usd)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(r.event_id, r.player_id, r.event_date, r.source, r.amount_usd) for r in events],
        )
        self._conn.commit()

    def insert_level_events(self, events: Iterable[LevelEvent]) -> None:
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO level_events (event_id, player_id, step_name, step_order, event_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            [(e.event_id, e.player_id, e.step_name, e.step_order, e.event_date) for e in events],
        )
        self._conn.commit()
