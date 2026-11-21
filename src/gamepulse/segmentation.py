from __future__ import annotations

from dataclasses import dataclass
from .storage import AnalyticsStore


@dataclass(frozen=True)
class SegmentBreakdownRow:
    segment: str
    player_count: int
    share_of_players_pct: float
    total_revenue_usd: float
    share_of_revenue_pct: float
    avg_sessions_per_player: float


@dataclass(frozen=True)
class RFMSegmentationReport:
    segments: tuple[SegmentBreakdownRow, ...]
    whale_revenue_share_pct: float
    at_risk_vip_count: int
    gini_revenue_coefficient: float


def _compute_gini(values: list[float]) -> float:
    positive = sorted(v for v in values if v >= 0)
    n = len(positive)
    total = sum(positive)
    if n == 0 or total <= 0:
        return 0.0
    weighted_sum = sum((idx + 1) * val for idx, val in enumerate(positive))
    gini = (2.0 * weighted_sum) / (n * total) - (n + 1.0) / n
    return round(max(0.0, min(1.0, gini)), 4)


def compute_rfm_segmentation(store: AnalyticsStore) -> RFMSegmentationReport:
    rows = store.connection.execute(
        """
        SELECT
            p.player_id,
            COALESCE(s.session_cnt, 0) AS session_count,
            COALESCE(r.total_rev, 0.0) AS total_spend
        FROM players p
        LEFT JOIN (
            SELECT player_id, COUNT(*) AS session_cnt
            FROM sessions
            GROUP BY player_id
        ) s ON s.player_id = p.player_id
        LEFT JOIN (
            SELECT player_id, SUM(amount_usd) AS total_rev
            FROM revenue_events
            GROUP BY player_id
        ) r ON r.player_id = p.player_id
        """
    ).fetchall()

    total_players = len(rows)
    if total_players == 0:
        return RFMSegmentationReport(
            segments=(),
            whale_revenue_share_pct=0.0,
            at_risk_vip_count=0,
            gini_revenue_coefficient=0.0,
        )

    buckets: dict[str, list[tuple[int, float]]] = {
        "whale": [],
        "at_risk_vip": [],
        "dolphin": [],
        "minnow": [],
        "non_payer": [],
    }
    all_spends: list[float] = []

    for row in rows:
        sessions = int(row["session_count"])
        spend = float(row["total_spend"])
        all_spends.append(spend)

        if spend >= 40.0 and sessions <= 2:
            buckets["at_risk_vip"].append((sessions, spend))
        elif spend >= 40.0:
            buckets["whale"].append((sessions, spend))
        elif spend >= 10.0:
            buckets["dolphin"].append((sessions, spend))
        elif spend > 0.0:
            buckets["minnow"].append((sessions, spend))
        else:
            buckets["non_payer"].append((sessions, spend))

    total_revenue = sum(all_spends)
    segment_rows: list[SegmentBreakdownRow] = []

    for seg_name in ("whale", "at_risk_vip", "dolphin", "minnow", "non_payer"):
        items = buckets[seg_name]
        count = len(items)
        rev = round(sum(x[1] for x in items), 2)
        avg_sess = round(sum(x[0] for x in items) / count, 2) if count > 0 else 0.0
        player_pct = round((count / total_players) * 100.0, 2)
        rev_pct = round((rev / total_revenue) * 100.0, 2) if total_revenue > 0 else 0.0
        segment_rows.append(
            SegmentBreakdownRow(
                segment=seg_name,
                player_count=count,
                share_of_players_pct=player_pct,
                total_revenue_usd=rev,
                share_of_revenue_pct=rev_pct,
                avg_sessions_per_player=avg_sess,
            )
        )

    whale_rev = sum(x[1] for x in buckets["whale"]) + sum(x[1] for x in buckets["at_risk_vip"])
    whale_share = round((whale_rev / total_revenue) * 100.0, 2) if total_revenue > 0 else 0.0

    return RFMSegmentationReport(
        segments=tuple(segment_rows),
        whale_revenue_share_pct=whale_share,
        at_risk_vip_count=len(buckets["at_risk_vip"]),
        gini_revenue_coefficient=_compute_gini(all_spends),
    )
