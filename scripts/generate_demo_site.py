from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gamepulse.api import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export live GamePulse dashboard + OpenAPI spec for GitHub Pages.")
    parser.add_argument("--out-dir", default=str(ROOT / "site"))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(db_path=":memory:", auto_seed=True)
    openapi_spec = app.openapi()
    (out_dir / "openapi.json").write_text(json.dumps(openapi_spec, indent=2), encoding="utf-8")

    dashboard_fn = next(route.endpoint for route in app.routes if getattr(route, "path", None) == "/")
    html_body: str = dashboard_fn()
    footer_banner = (
        '<div style="max-width:1080px;margin:20px auto 0;padding:12px 16px;'
        'background:#14112B;border:1px solid #2A2452;border-radius:10px;'
        'display:flex;justify-content:space-between;align-items:center;font-size:13px;color:#94A3B8;">'
        '<span>Static snapshot generated from 1,200 seeded players via <code>gamepulse.api:create_app()</code></span>'
        '<a href="./openapi.json" style="color:#38BDF8;text-decoration:none;font-weight:600;">View OpenAPI 3.1 JSON →</a>'
        '</div></body>'
    )
    html_body = html_body.replace("</body>", footer_banner)
    (out_dir / "index.html").write_text(html_body, encoding="utf-8")
    app.state.store.close()
    print(f"Generated {out_dir / 'index.html'} and {out_dir / 'openapi.json'}")


if __name__ == "__main__":
    main()
