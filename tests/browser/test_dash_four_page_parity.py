from __future__ import annotations

import json
import socket
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Page, sync_playwright

from portfell.dash_app.app import mount_dash_app
from portfell.dash_app.visual_contract import PAGE_ROUTES, REFERENCE_URL, VISUAL_VIEWPORTS
from tests.browser.dash_fixture_service import DashParityFixtureService


@pytest.mark.browser
def test_dash_four_page_journey_and_visual_evidence(tmp_path: Path) -> None:
    service = DashParityFixtureService()
    api = FastAPI()

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_dash_app(api, services=service)
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    )
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    _wait_started(server)
    base_url = f"http://127.0.0.1:{port}"
    evidence_dir = tmp_path / "dash-parity-v1"
    evidence_dir.mkdir(parents=True)
    screenshots: list[dict[str, object]] = []
    console_errors: list[str] = []
    page_errors: list[str] = []
    reference_requests: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on(
                "console",
                lambda message: console_errors.append(message.text) if message.type == "error" else None,
            )
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "request",
                lambda request: reference_requests.append(request.url)
                if "financial-dashboard-example.plotly.app" in request.url
                else None,
            )

            page.goto(f"{base_url}/metadata", wait_until="networkidle")
            _assert_shell(page, "Metadata")
            page.locator("#metadata-create-universe").click()
            page.locator("#metadata-continue-univariate[aria-disabled='false']").wait_for()
            page.locator("#metadata-continue-univariate").click()

            page.wait_for_url(f"{base_url}/univariate")
            _assert_shell(page, "Univariate")
            page.locator("#univariate-compute").click()
            page.wait_for_function("document.body.innerText.includes('DE000TEST01')")
            page.locator("#univariate-save-selection").click()
            page.locator("#univariate-continue-bivariate[aria-disabled='false']").wait_for()
            page.locator("#univariate-continue-bivariate").click()

            page.wait_for_url(f"{base_url}/bivariate")
            _assert_shell(page, "Bivariate")
            page.locator("#bivariate-compute").click()
            page.locator("#bivariate-continue-multivariate[aria-disabled='false']").wait_for()
            page.locator("#bivariate-continue-multivariate").click()

            page.wait_for_url(f"{base_url}/multivariate")
            _assert_shell(page, "Multivariate")
            page.locator("#multivariate-optimize").click()
            page.wait_for_function("document.body.innerText.includes('candidate-fixture')")
            assert "minimum_variance" in page.locator("body").inner_text()

            for viewport in VISUAL_VIEWPORTS:
                page.set_viewport_size({"width": viewport.width, "height": viewport.height})
                for route in PAGE_ROUTES:
                    page.goto(f"{base_url}{route}", wait_until="networkidle")
                    title = route.removeprefix("/").title()
                    _assert_shell(page, title)
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= window.innerWidth"
                    )
                    screenshot = evidence_dir / f"{viewport.name}-{route.removeprefix('/')}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    screenshots.append(
                        {
                            "route": route,
                            "viewport": viewport.name,
                            "width": viewport.width,
                            "height": viewport.height,
                            "file": screenshot.name,
                        }
                    )
            browser.close()

        assert not console_errors
        assert not page_errors
        assert not reference_requests
        evidence = {
            "contract": "dash-parity-v1",
            "status": "PASS",
            "routes": list(PAGE_ROUTES),
            "reference_url": REFERENCE_URL,
            "reference_runtime_requests": reference_requests,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "assertions": {
                "workflow_journey": True,
                "exact_four_routes": True,
                "reference_network_dependency_absent": True,
                "body_horizontal_overflow_absent": True,
                "screenshots_complete": len(screenshots) == 12,
            },
            "screenshots": screenshots,
        }
        (evidence_dir / "dash-parity-v1.json").write_text(
            json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        assert evidence["assertions"]["screenshots_complete"] is True
    finally:
        server.should_exit = True
        thread.join(timeout=10)


def _assert_shell(page: Page, title: str) -> None:
    page.locator("#pf-main-content").wait_for()
    body = page.locator("body").inner_text()
    assert "Portfell" in body
    assert title in body
    links = page.locator(".pf-navigation .pf-nav-link")
    assert links.all_inner_texts() == ["Metadata", "Univariate", "Bivariate", "Multivariate"]
    assert page.locator(".pf-nav-link-active").count() == 1
    for forbidden in ("Price Performance", "Fees & Distributions", "Resources"):
        assert forbidden not in body


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_started(server: uvicorn.Server) -> None:
    deadline = monotonic() + 10
    while not server.started and monotonic() < deadline:
        sleep(0.05)
    if not server.started:
        raise RuntimeError("dash parity server did not start")
