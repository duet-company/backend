"""
Test Report Generator

Generates comprehensive test reports from pytest results.
"""

import json
import time
from typing import Dict, List, Any
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    status: str  # passed, failed, skipped, error
    duration: float
    markers: List[str]
    error_message: str = ""


@dataclass
class SuiteReport:
    """Represents a test suite report."""
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    test_results: List[TestResult]
    by_marker: Dict[str, Dict[str, int]]
    performance_metrics: Dict[str, Any]


class TestReportGenerator:
    """Generates test reports in multiple formats."""

    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = time.time()
        self.marker_stats = defaultdict(lambda: {"passed": 0, "failed": 0, "skipped": 0, "errors": 0})
        self.performance_data = {}

    def add_result(self, name: str, status: str, duration: float, markers: List[str], error: str = ""):
        """Add a test result."""
        result = TestResult(name=name, status=status, duration=duration, markers=markers, error_message=error)
        self.results.append(result)
        
        # Update marker stats
        for marker in markers:
            self.marker_stats[marker][status] += 1

    def add_performance_metric(self, name: str, value: float, unit: str = "ms"):
        """Add performance metric."""
        if name not in self.performance_data:
            self.performance_data[name] = []
        self.performance_data[name].append({"value": value, "unit": unit})

    def generate_summary(self) -> SuiteReport:
        """Generate summary report."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        skipped = sum(1 for r in self.results if r.status == "skipped")
        errors = sum(1 for r in self.results if r.status == "error")
        
        # Calculate aggregate performance metrics
        performance_summary = {}
        for metric_name, values in self.performance_data.items():
            numeric_values = [v["value"] for v in values]
            if numeric_values:
                performance_summary[metric_name] = {
                    "avg": sum(numeric_values) / len(numeric_values),
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "count": len(numeric_values),
                    "unit": values[0]["unit"]
                }
        
        return SuiteReport(
            total_tests=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            duration=time.time() - self.start_time,
            test_results=self.results,
            by_marker=dict(self.marker_stats),
            performance_metrics=performance_summary
        )

    def generate_console_report(self, report: SuiteReport) -> str:
        """Generate console-friendly report."""
        lines = []
        lines.append("=" * 80)
        lines.append("TEST REPORT SUMMARY")
        lines.append("=" * 80)
        
        # Overall stats
        lines.append(f"\n📊 Overall Results:")
        lines.append(f"   Total Tests: {report.total_tests}")
        lines.append(f"   ✅ Passed: {report.passed} ({(report.passed/report.total_tests*100):.1f}%)")
        lines.append(f"   ❌ Failed: {report.failed} ({(report.failed/report.total_tests*100):.1f}%)")
        lines.append(f"   ⏭️  Skipped: {report.skipped} ({(report.skipped/report.total_tests*100):.1f}%)")
        lines.append(f"   💥 Errors: {report.errors} ({(report.errors/report.total_tests*100):.1f}%)")
        lines.append(f"   ⏱️  Duration: {report.duration:.2f}s")
        
        # By marker
        if report.by_marker:
            lines.append(f"\n📈 Results by Test Type:")
            for marker, stats in sorted(report.by_marker.items()):
                total = sum(stats.values())
                lines.append(f"   {marker}:")
                lines.append(f"      ✅ {stats['passed']}/{total} passed")
                if stats['failed'] > 0:
                    lines.append(f"      ❌ {stats['failed']}/{total} failed")
                if stats['errors'] > 0:
                    lines.append(f"      💥 {stats['errors']}/{total} errors")
        
        # Performance metrics
        if report.performance_metrics:
            lines.append(f"\n⚡ Performance Metrics:")
            for metric_name, data in sorted(report.performance_metrics.items()):
                unit = data['unit']
                lines.append(f"   {metric_name}:")
                lines.append(f"      Average: {data['avg']:.2f}{unit}")
                lines.append(f"      Min: {data['min']:.2f}{unit}")
                lines.append(f"      Max: {data['max']:.2f}{unit}")
                lines.append(f"      Samples: {data['count']}")
        
        # Failed tests
        failed_tests = [r for r in report.test_results if r.status in ["failed", "error"]]
        if failed_tests:
            lines.append(f"\n❌ Failed Tests ({len(failed_tests)}):")
            for test in failed_tests[:20]:  # Show first 20
                lines.append(f"   ❌ {test.name}")
                if test.error_message:
                    lines.append(f"      {test.error_message[:100]}")
            
            if len(failed_tests) > 20:
                lines.append(f"   ... and {len(failed_tests) - 20} more failures")
        
        # Slowest tests
        sorted_by_duration = sorted(report.test_results, key=lambda x: x.duration, reverse=True)
        slowest = sorted_by_duration[:10]
        lines.append(f"\n🐢 Slowest Tests:")
        for test in slowest:
            lines.append(f"   {test.name}: {test.duration:.2f}s")
        
        lines.append("\n" + "=" * 80)
        
        return "\n".join(lines)

    def generate_json_report(self, report: SuiteReport) -> str:
        """Generate JSON report."""
        return json.dumps({
            "summary": {
                "total_tests": report.total_tests,
                "passed": report.passed,
                "failed": report.failed,
                "skipped": report.skipped,
                "errors": report.errors,
                "duration_seconds": report.duration,
                "success_rate": report.passed / report.total_tests if report.total_tests > 0 else 0
            },
            "by_marker": report.by_marker,
            "performance_metrics": report.performance_metrics,
            "failed_tests": [
                {
                    "name": r.name,
                    "status": r.status,
                    "duration": r.duration,
                    "error": r.error_message
                }
                for r in report.test_results if r.status in ["failed", "error"]
            ],
            "slowest_tests": [
                {
                    "name": r.name,
                    "duration": r.duration
                }
                for r in sorted(report.test_results, key=lambda x: x.duration, reverse=True)[:10]
            ]
        }, indent=2)

    def generate_markdown_report(self, report: SuiteReport) -> str:
        """Generate Markdown report."""
        lines = []
        
        lines.append("# Test Report")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Tests**: {report.total_tests}")
        lines.append(f"- **Passed**: {report.passed} ({(report.passed/report.total_tests*100):.1f}%)")
        lines.append(f"- **Failed**: {report.failed} ({(report.failed/report.total_tests*100):.1f}%)")
        lines.append(f"- **Skipped**: {report.skipped} ({(report.skipped/report.total_tests*100):.1f}%)")
        lines.append(f"- **Errors**: {report.errors} ({(report.errors/report.total_tests*100):.1f}%)")
        lines.append(f"- **Duration**: {report.duration:.2f}s")
        
        if report.by_marker:
            lines.append("")
            lines.append("## Results by Test Type")
            lines.append("")
            lines.append("| Test Type | Passed | Failed | Errors | Total |")
            lines.append("|-----------|--------|--------|--------|-------|")
            
            for marker, stats in sorted(report.by_marker.items()):
                total = sum(stats.values())
                lines.append(f"| {marker} | {stats['passed']} | {stats['failed']} | {stats['errors']} | {total} |")
        
        if report.performance_metrics:
            lines.append("")
            lines.append("## Performance Metrics")
            lines.append("")
            
            for metric_name, data in sorted(report.performance_metrics.items()):
                unit = data['unit']
                lines.append(f"### {metric_name}")
                lines.append("")
                lines.append(f"- Average: {data['avg']:.2f}{unit}")
                lines.append(f"- Minimum: {data['min']:.2f}{unit}")
                lines.append(f"- Maximum: {data['max']:.2f}{unit}")
                lines.append(f"- Samples: {data['count']}")
                lines.append("")
        
        failed_tests = [r for r in report.test_results if r.status in ["failed", "error"]]
        if failed_tests:
            lines.append("## Failed Tests")
            lines.append("")
            for test in failed_tests[:20]:
                lines.append(f"### ❌ {test.name}")
                lines.append("")
                lines.append(f"- **Status**: {test.status}")
                lines.append(f"- **Duration**: {test.duration:.2f}s")
                if test.error_message:
                    lines.append(f"- **Error**: ```")
                    lines.append(test.error_message)
                    lines.append("```")
                lines.append("")
        
        return "\n".join(lines)


# Global instance for pytest hooks
report_generator = TestReportGenerator()


def pytest_runtest_makereport(item, call):
    """Pytest hook to collect test results.

    Handles all test phases: setup, call, and teardown.
    Skipped tests are skipped during setup, so we check that phase first.
    """
    # Track if we've already recorded this test (to avoid duplicates)
    if hasattr(item, '_report_recorded'):
        return

    status = None
    duration = call.duration if hasattr(call, 'duration') else 0
    error_message = ""

    if call.when == "setup":
        # Handle tests skipped during setup
        if hasattr(call, 'excinfo') and call.excinfo is not None:
            if hasattr(call.excinfo, 'value'):
                # Check if it's a skip exception
                if call.excinfo.typename == "Skipped":
                    status = "skipped"
                    error_message = str(call.excinfo.value) if hasattr(call.excinfo.value, '__str__') else ""
                # Check if it's an error during setup
                elif call.excinfo.typename in ["Error", "Exception", "SetupError"]:
                    status = "error"
                    error_message = f"{call.excinfo.typename}: {call.excinfo.value}"

    elif call.when == "call":
        # Handle normal test execution
        if hasattr(call, 'excinfo'):
            if call.excinfo is None:
                status = "passed"
            else:
                # Check if it's an explicit skip during call
                if call.excinfo.typename == "Skipped":
                    status = "skipped"
                    error_message = str(call.excinfo.value) if hasattr(call.excinfo.value, '__str__') else ""
                # Check if it's an error
                elif call.excinfo.typename == "Error":
                    status = "error"
                    error_message = f"{call.excinfo.typename}: {call.excinfo.value}"
                # Otherwise it's a failure
                else:
                    status = "failed"
                    error_message = str(call.excinfo.value) if hasattr(call.excinfo.value, '__str__') else ""
        else:
            status = "passed"

    elif call.when == "teardown":
        # Handle errors during teardown
        if hasattr(call, 'excinfo') and call.excinfo is not None:
            status = "error"
            error_message = f"Teardown {call.excinfo.typename}: {call.excinfo.value}"
            duration = call.duration if hasattr(call, 'duration') else 0

    # Only record if we determined a status
    if status is not None:
        markers = [marker.name for marker in item.iter_markers()]

        # Extract performance data from test report if available
        if hasattr(call, "result") and call.result:
            # Try to extract performance metrics from test output
            pass

        report_generator.add_result(
            name=item.nodeid,
            status=status,
            duration=duration,
            markers=markers,
            error=error_message
        )

        # Mark this test as recorded to avoid duplicates
        item._report_recorded = True


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Pytest hook to generate report at end of test run."""
    report = report_generator.generate_summary()
    
    # Print console report
    print("\n")
    print(report_generator.generate_console_report(report))
    
    # Save JSON report
    try:
        with open("test-report.json", "w") as f:
            f.write(report_generator.generate_json_report(report))
        print("\n💾 JSON report saved to: test-report.json")
    except Exception as e:
        print(f"\n⚠️  Failed to save JSON report: {e}")
    
    # Save Markdown report
    try:
        with open("test-report.md", "w") as f:
            f.write(report_generator.generate_markdown_report(report))
        print("💾 Markdown report saved to: test-report.md")
    except Exception as e:
        print(f"⚠️  Failed to save Markdown report: {e}")
