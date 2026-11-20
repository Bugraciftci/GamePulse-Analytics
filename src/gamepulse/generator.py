from __future__ import annotations

import datetime
import random

from .models import LevelEvent, PlayerProfile, RevenueEvent, SessionEvent
from .storage import AnalyticsStore


def seed_synthetic_dataset(
    store: AnalyticsStore,
    player_count: int = 1200,
    cohort_days: int = 7,
    seed: int = 42,
) -> dict[str, int]:
    """Seeds realistic mobile-game player telemetry (retention decay, IAP whales, rewarded ads, funnel & A/B uplift)."""
    rng = random.Random(seed)
    start_date = datetime.date(2026, 10, 1)

    channels = [
        ("apple_search_ads", 2.40, 0.40),
        ("meta_ua", 1.85, 0.35),
        ("organic", 0.00, 0.25),
    ]
    countries = ["US", "TR", "GB", "DE", "JP"]
    funnel_steps = [
        ("install", 1, 1.00),
        ("tutorial_complete", 2, 0.82),
        ("level_1_clear", 3, 0.74),
        ("level_5_clear", 4, 0.48),
        ("first_purchase", 5, 0.16),
    ]

    players: list[PlayerProfile] = []
    sessions: list[SessionEvent] = []
    revenues: list[RevenueEvent] = []
    levels: list[LevelEvent] = []

    sess_id = 0
    rev_id = 0
    lvl_id = 0

    for i in range(player_count):
        pid = f"p_{i:05d}"
        day_idx = i % cohort_days
        install_dt = start_date + datetime.timedelta(days=day_idx)
        install_str = install_dt.isoformat()

        r = rng.random()
        if r < 0.40:
            channel, cpi = channels[0][0], channels[0][1]
        elif r < 0.75:
            channel, cpi = channels[1][0], channels[1][1]
        else:
            channel, cpi = channels[2][0], channels[2][1]

        group = "treatment" if i % 2 == 1 else "control"
        country = rng.choice(countries)

        players.append(
            PlayerProfile(
                player_id=pid,
                install_date=install_str,
                channel=channel,
                country=country,
                experiment_group=group,
                cpi_usd=cpi,
            )
        )

        # D0 session
        sess_id += 1
        sessions.append(SessionEvent(f"s_{sess_id}", pid, install_str, rng.randint(180, 1400)))

        # Retention decay probabilities (treatment has modest positive uplift)
        boost = 1.12 if group == "treatment" else 1.0
        for offset, base_prob in ((1, 0.42), (3, 0.28), (7, 0.19), (14, 0.12), (30, 0.07)):
            if rng.random() < min(base_prob * boost, 0.95):
                sess_id += 1
                s_date = (install_dt + datetime.timedelta(days=offset)).isoformat()
                sessions.append(SessionEvent(f"s_{sess_id}", pid, s_date, rng.randint(120, 1800)))

                # Rewarded ad micro-revenue
                if rng.random() < 0.35:
                    rev_id += 1
                    revenues.append(RevenueEvent(f"r_{rev_id}", pid, s_date, "ad_rewarded", round(rng.uniform(0.04, 0.18), 2)))

        # Funnel progression
        progressed = True
        for step_name, step_order, keep_prob in funnel_steps:
            effective_prob = keep_prob * (1.18 if (step_name == "first_purchase" and group == "treatment") else 1.0)
            if step_order == 1 or (progressed and rng.random() < min(effective_prob, 0.98)):
                lvl_id += 1
                levels.append(LevelEvent(f"l_{lvl_id}", pid, step_name, step_order, install_str))
                if step_name == "first_purchase":
                    # Realistic mobile game SKU distribution (minnow / dolphin / whale)
                    sku = rng.choices([4.99, 9.99, 19.99, 49.99], weights=[55, 28, 13, 4], k=1)[0]
                    rev_id += 1
                    revenues.append(RevenueEvent(f"r_{rev_id}", pid, install_str, "iap", sku))
            else:
                progressed = False

    store.insert_players(players)
    store.insert_sessions(sessions)
    store.insert_revenue(revenues)
    store.insert_level_events(levels)

    return {
        "players": len(players),
        "sessions": len(sessions),
        "revenue_events": len(revenues),
        "level_events": len(levels),
    }
