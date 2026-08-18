import re
from html.parser import HTMLParser
from pathlib import Path

import paircue


class DashboardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if tag == "script" and values.get("src"):
            self.scripts.append(str(values["src"]))
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.stylesheets.append(str(values["href"]))


def _dashboard_root() -> Path:
    return Path(paircue.__file__).with_name("dashboard")


def test_dashboard_is_self_contained_and_does_not_store_its_token() -> None:
    root = _dashboard_root()
    html = (root / "index.html").read_text(encoding="utf-8")
    javascript = (root / "dashboard.js").read_text(encoding="utf-8")
    parser = DashboardParser()
    parser.feed(html)

    assert parser.scripts == ["/dashboard.js"]
    assert parser.stylesheets == ["/dashboard.css"]
    assert len(parser.ids) == len(set(parser.ids))
    assert not re.search(r"(?:src|href)=[\"']https?://", html)
    assert not re.search(r"\b(localStorage|sessionStorage|sendBeacon|WebSocket)\b", javascript)
    assert 'Authorization: `Bearer ${token}`' in javascript
    assert 'history.replaceState(null, "",' in javascript
    assert 'byId("working-count").textContent = String(payload.pending);' in javascript


def test_dashboard_javascript_only_references_existing_elements() -> None:
    root = _dashboard_root()
    html = (root / "index.html").read_text(encoding="utf-8")
    javascript = (root / "dashboard.js").read_text(encoding="utf-8")
    parser = DashboardParser()
    parser.feed(html)
    referenced_ids = set(re.findall(r'byId\("([A-Za-z0-9-]+)"\)', javascript))

    assert referenced_ids <= set(parser.ids)
