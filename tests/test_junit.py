from pathlib import Path

from evaluator.junit import parse_junit


def test_parse_junit(tmp_path: Path):
    xml = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="3" errors="1" failures="1" skipped="0">
  <testcase classname="t" name="ok" time="0.01"/>
  <testcase classname="t" name="bad" time="0.01">
    <failure message="assert 1 == 2">fail</failure>
  </testcase>
  <testcase classname="t" name="boom" time="0.01">
    <error message="boom">err</error>
  </testcase>
</testsuite>
"""
    path = tmp_path / "junit.xml"
    path.write_text(xml, encoding="utf-8")
    summary = parse_junit(path)
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["errors"] == 1
    assert summary["total"] == 3
