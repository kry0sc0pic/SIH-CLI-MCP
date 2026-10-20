import json

import pytest

from sih import core


def _row(n, org, title, cat, num, ideas, theme, deadline, desc, dataset=""):
    pid = num.removeprefix("SIH")
    return f"""
<tr><td>{n}</td><td>{org}</td>
<td><a data-target="#ViewProblemStatement{pid}">{title}</a>
<div id="ViewProblemStatement{pid}" class="modal"><div class="modal-body"><table><thead>
<tr><th>Problem Statement ID</th><td><div> {pid}</div></td></tr>
<tr><th>Problem Statement Title</th><td><div> {title}</div></td></tr>
<tr><th>Description</th><td><!-- <div>&lt;p&gt;old&lt;/p&gt;</div> --><div><p>{desc}</p></div></td></tr>
<tr><th>Organization</th><td>{org}</td></tr>
<tr><th>Department</th><td> Dept of {org} </td></tr>
<tr><th>Category</th><td>{cat}</td></tr>
<tr><th>Theme</th><td>{theme}</td></tr>
<tr><th>Youtube Link</th><td><a href=" "> </a></td></tr>
<tr><th>Dataset Link</th><td>{dataset}</td></tr>
<tr><th>Contact info</th><td><a href=" "> </a></td></tr>
</thead></table></div></div></td>
<td>{cat}</td><td>{num}</td><td>{ideas}</td><td>{theme}</td><td>{deadline}</td></tr>"""


ROWS = [
    (1, "AICTE", "Drone swarm for farms", "software", "SIH1001", "3/500", "Agriculture", "28 October 2026", "Use drones and AI for crops.", '<a href="https://x.test/data">d</a>'),
    (2, "ISRO", "Satellite telemetry parser", "Hardware", "SIH1002", "0", "Space Technology", "05 October 2026", "Parse telemetry frames."),
    (3, "NTRO", "Cyber threat triage", "Software", "SIH1010", "12/500", "Blockchain & Cybersecurity", "20 October 2026", "Triage alerts with ai models."),
    (4, "AICTE", "Campus portal", "Software", "SIH1003", "7/500", "Smart Automation", "garbage date", "Tribal affairs portal."),
]


@pytest.fixture(scope="session")
def html():
    body = "".join(_row(*r) for r in ROWS)
    return f"<html><body><table id='dataTablePS'><thead><tr><th>S</th></tr></thead><tbody>{body}</tbody></table></body></html>"


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch, html):
    monkeypatch.setattr(core, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(core, "CACHE_FILE", tmp_path / "ps.json")
    calls = []

    class Resp:
        text = html

        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        calls.append(url)
        return Resp()

    monkeypatch.setattr(core.httpx, "get", fake_get)
    return calls


@pytest.fixture
def fetch_calls(isolated_cache):
    return isolated_cache
