"""Run the pytest suite with coverage and parse the results for the UI.

Runs in a subprocess (isolated from the Streamlit process) and returns a
structured dict the Tests tab renders: per-test pass/fail and per-file coverage.
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, Any, List


def _parse_junit(path: str) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    # Root may be <testsuites> or a single <testsuite>.
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    cases: List[Dict[str, Any]] = []
    totals = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0, "duration": 0.0}
    for suite in suites:
        totals["duration"] += float(suite.get("time", 0) or 0)
        for case in suite.findall("testcase"):
            status, message = "passed", ""
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            if failure is not None:
                status, message = "failed", (failure.get("message") or "").strip()
            elif error is not None:
                status, message = "error", (error.get("message") or "").strip()
            elif skipped is not None:
                status, message = "skipped", (skipped.get("message") or "").strip()
            totals["total"] += 1
            totals[{"passed": "passed", "failed": "failed",
                    "error": "errors", "skipped": "skipped"}[status]] += 1
            cases.append({
                "name": case.get("name"),
                "suite": case.get("classname", ""),
                "time": round(float(case.get("time", 0) or 0), 3),
                "status": status,
                "message": message[:300],
            })
    return {"totals": totals, "cases": cases}


def _parse_coverage(path: str) -> Dict[str, Any]:
    with open(path) as f:
        data = json.load(f)
    files = []
    for fname, info in data.get("files", {}).items():
        summ = info.get("summary", {})
        files.append({
            "file": fname.replace("\\", "/"),
            "percent": round(summ.get("percent_covered", 0), 1),
            "covered": summ.get("covered_lines", 0),
            "statements": summ.get("num_statements", 0),
            "missing": summ.get("missing_lines", 0),
        })
    files.sort(key=lambda x: x["percent"])
    return {
        "total_percent": round(data.get("totals", {}).get("percent_covered", 0), 1),
        "files": files,
    }


def run_test_suite(project_root: str, timeout: int = 180) -> Dict[str, Any]:
    """Run `coverage run -m pytest` then `coverage json`; return parsed results."""
    reports = os.path.join(project_root, "reports")
    os.makedirs(reports, exist_ok=True)
    junit = os.path.join(reports, "junit.xml")
    cov_json = os.path.join(reports, "coverage.json")
    py = sys.executable

    try:
        proc = subprocess.run(
            [py, "-m", "coverage", "run", "--source=core", "-m",
             "pytest", "tests", "-q", f"--junit-xml={junit}"],
            cwd=project_root, capture_output=True, text=True, timeout=timeout,
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except FileNotFoundError:
        return {"ok": False, "error": "pytest/coverage not installed. "
                "Run: pip install pytest coverage"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Test run timed out after {timeout}s."}

    result: Dict[str, Any] = {"ok": True, "output": output[-4000:]}

    if os.path.exists(junit):
        try:
            result["tests"] = _parse_junit(junit)
        except Exception as e:
            result["tests"] = None
            result["error"] = f"Could not parse test results: {e}"
    else:
        result["ok"] = False
        result["error"] = "No test report produced. See output below."

    # Coverage report (best effort).
    try:
        subprocess.run([py, "-m", "coverage", "json", "-o", cov_json, "-q"],
                       cwd=project_root, capture_output=True, text=True, timeout=60)
        if os.path.exists(cov_json):
            result["coverage"] = _parse_coverage(cov_json)
    except Exception:
        result["coverage"] = None

    return result
