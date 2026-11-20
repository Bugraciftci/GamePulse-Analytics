<div align="center">
  <img src="./assets/banner.svg" width="100%" alt="GamePulse-Analytics Banner" />
</div>

<p align="center">
  <img src="https://img.shields.io/badge/Python_3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/SQLite_SQL-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
</p>

Mobile game and consumer app **product analytics, monetization modeling, and statistical A/B experimentation engine** built with Python, indexed SQLite analytical queries, and FastAPI.

## Architecture

```mermaid
flowchart LR
    GEN["Seeded Telemetry Simulator<br/>Players · Sessions · IAP · Ads · Levels"] --> DB[(Indexed SQLite Store)]
    DB --> RET["SQL Cohort Retention<br/>D1 · D3 · D7 · D14 · D30"]
    DB --> LTV["Monetization Engine<br/>ARPU · ARPPU · ARPDAU · ROAS · Payback"]
    DB --> FUN["Progression Funnel<br/>Drop-Off & Bottleneck Detector"]
    DB --> AB["Frequentist A/B Engine<br/>Two-Proportion Z-Test · 95% CI · SRM"]
    RET & LTV & FUN & AB --> API["FastAPI REST API + Dark Dashboard"]
```

## Core Capabilities

- **SQL Cohort Retention Matrix (`compute_cohort_retention`):** Computes D1, D3, D7, D14, and D30 retention curves via SQLite CTEs & `julianday` offsets, filterable by acquisition channel (`apple_search_ads`, `meta_ua`, `organic`).
- **LTV, ROAS & Payback Modeling (`compute_ltv_summary`):** Calculates Payer Conversion %, ARPU, ARPPU, ARPDAU, campaign ROAS %, and estimated CPI payback days.
- **Funnel Bottleneck Diagnostics (`compute_funnel_report`):** Tracks step-to-step onboarding/level conversion and automatically identifies the steepest drop-off bottleneck.
- **Zero-SciPy Statistical A/B Test Engine (`analyze_ab_test`):** Two-proportion Z-test using standard-library `math.erf`, two-tailed p-value, 95% Wald confidence interval, and a **Chi-Square Sample Ratio Mismatch (SRM)** guard that invalidates skewed splits automatically.
- **Live FastAPI REST API & Executive Dashboard:** Exposes `/api/retention`, `/api/monetization`, `/api/funnel`, `/api/experiments/paywall`, and a dark-mode executive UI at `/`.

## Quick Start

```bash
git clone https://github.com/Bugraciftci/GamePulse-Analytics.git
cd GamePulse-Analytics
pip install -r requirements.txt

# Launch FastAPI dashboard on http://127.0.0.1:8000
PYTHONPATH=src uvicorn gamepulse.api:app --reload
```

### Run Tests

```bash
python3 -m unittest discover -s tests -v
```

### Run with Docker

```bash
docker build -t gamepulse-analytics .
docker run -p 8000:8000 gamepulse-analytics
```

## License

MIT — see [LICENSE](./LICENSE).
