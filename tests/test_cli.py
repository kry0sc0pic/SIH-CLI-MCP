import json

from typer.testing import CliRunner

from sih.cli import app

runner = CliRunner()


def test_refresh():
    r = runner.invoke(app, ["refresh"])
    assert r.exit_code == 0 and "Fetched 4" in r.output


def test_search_json_filters():
    r = runner.invoke(app, ["search", "ai", "--category", "software", "--sort", "ideas", "--desc", "--json"])
    assert r.exit_code == 0, r.output
    d = json.loads(r.output)
    assert d["total"] == 2
    assert [x["ps_number"] for x in d["results"]] == ["SIH1010", "SIH1001"]


def test_search_deadline_options():
    r = runner.invoke(app, ["search", "--from", "2026-10-20", "--to", "2026-10-25", "--json"])
    assert [x["ps_number"] for x in json.loads(r.output)["results"]] == ["SIH1010"]


def test_search_table():
    r = runner.invoke(app, ["search", "--org", "isro"], env={"COLUMNS": "200"})
    assert r.exit_code == 0 and "SIH1002" in r.output and "1 of 1" in r.output


def test_show():
    r = runner.invoke(app, ["show", "SIH1001"])
    assert r.exit_code == 0 and "Drone swarm" in r.output and "x.test/data" in r.output
    j = json.loads(runner.invoke(app, ["show", "1001", "--json"]).output)
    assert j["ps_id"] == "1001"


def test_show_missing():
    assert runner.invoke(app, ["show", "SIH9999"]).exit_code != 0


def test_facets():
    r = runner.invoke(app, ["facets"], env={"COLUMNS": "200"})
    assert r.exit_code == 0 and "Total: 4" in r.output and "AICTE" in r.output


def test_search_bad_sort_fails():
    assert runner.invoke(app, ["search", "--sort", "bogus"]).exit_code != 0
