"""Parse pytest JUnit XML into a compact summary."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .state import TestSummary


def parse_junit(path: Path | str) -> TestSummary:
    file_path = Path(path)
    if not file_path.exists():
        return TestSummary(passed=0, failed=0, errors=0, total=0, details=[])

    tree = ET.parse(file_path)
    root = tree.getroot()

    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites and root.tag == "testsuites":
        suites = list(root)

    passed = failed = errors = total = 0
    details: list[dict] = []

    for suite in suites:
        for case in suite.findall("testcase"):
            total += 1
            name = case.get("name") or "unknown"
            classname = case.get("classname") or ""
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            if failure is not None:
                failed += 1
                details.append(
                    {
                        "name": name,
                        "classname": classname,
                        "status": "failed",
                        "message": (failure.get("message") or failure.text or "")[:500],
                    }
                )
            elif error is not None:
                errors += 1
                details.append(
                    {
                        "name": name,
                        "classname": classname,
                        "status": "error",
                        "message": (error.get("message") or error.text or "")[:500],
                    }
                )
            elif skipped is not None:
                details.append(
                    {
                        "name": name,
                        "classname": classname,
                        "status": "skipped",
                        "message": (skipped.get("message") or "")[:500],
                    }
                )
            else:
                passed += 1
                details.append({"name": name, "classname": classname, "status": "passed"})

    return TestSummary(
        passed=passed,
        failed=failed,
        errors=errors,
        total=total,
        details=details,
    )
