#!/usr/bin/env python3
"""
Compare two baseline measurements to detect performance regressions.

Used during refactoring to validate that performance stays within ±5% tolerance.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass


@dataclass
class ComparisonResult:
    """Result of comparing two baseline measurements."""

    task_type: str
    baseline_p95: float
    current_p95: float
    delta_ms: float
    delta_percent: float
    within_tolerance: bool
    baseline_memory: float
    current_memory: float
    memory_delta_percent: float


class BaselineComparator:
    """Compare baseline performance measurements."""

    def __init__(self, tolerance_percent: float = 5.0):
        self.tolerance_percent = tolerance_percent

    def load_metrics(self, path: str) -> dict:
        """Load aggregated metrics from JSON file."""
        with open(path) as f:
            data = json.load(f)

        # Convert list to dict keyed by operation_name
        if isinstance(data, list):
            return {item["operation_name"]: item for item in data}
        return data

    def compare(
        self,
        baseline_path: str,
        current_path: str,
    ) -> list[ComparisonResult]:
        """
        Compare baseline and current metrics.

        Args:
            baseline_path: Path to baseline aggregated metrics JSON
            current_path: Path to current aggregated metrics JSON

        Returns:
            List of comparison results per task type
        """
        baseline = self.load_metrics(baseline_path)
        current = self.load_metrics(current_path)

        results = []

        # Get all task types from both baselines
        all_tasks = set(baseline.keys()) | set(current.keys())

        for task_type in sorted(all_tasks):
            baseline_metrics = baseline.get(task_type)
            current_metrics = current.get(task_type)

            if not baseline_metrics:
                print(f"Warning: {task_type} not in baseline", file=sys.stderr)
                continue

            if not current_metrics:
                print(f"Warning: {task_type} not in current", file=sys.stderr)
                continue

            # Extract P95 latencies
            baseline_p95 = baseline_metrics.get("p95_duration_ms", 0.0)
            current_p95 = current_metrics.get("p95_duration_ms", 0.0)

            # Calculate delta
            delta_ms = current_p95 - baseline_p95
            delta_percent = (delta_ms / baseline_p95 * 100) if baseline_p95 > 0 else 0.0

            # Check tolerance
            within_tolerance = abs(delta_percent) <= self.tolerance_percent

            # Memory comparison
            baseline_memory = baseline_metrics.get("avg_memory_delta_mb", 0.0)
            current_memory = current_metrics.get("avg_memory_delta_mb", 0.0)
            memory_delta_percent = (
                ((current_memory - baseline_memory) / baseline_memory * 100) if baseline_memory > 0 else 0.0
            )

            results.append(
                ComparisonResult(
                    task_type=task_type,
                    baseline_p95=baseline_p95,
                    current_p95=current_p95,
                    delta_ms=delta_ms,
                    delta_percent=delta_percent,
                    within_tolerance=within_tolerance,
                    baseline_memory=baseline_memory,
                    current_memory=current_memory,
                    memory_delta_percent=memory_delta_percent,
                )
            )

        return results

    def print_summary(self, results: list[ComparisonResult]) -> None:
        """Print human-readable comparison summary."""
        print("\n" + "=" * 80)
        print("PERFORMANCE BASELINE COMPARISON")
        print("=" * 80 + "\n")

        # Summary stats
        total = len(results)
        within_tolerance = sum(1 for r in results if r.within_tolerance)
        regressions = sum(1 for r in results if r.delta_percent > self.tolerance_percent)
        improvements = sum(1 for r in results if r.delta_percent < -self.tolerance_percent)

        print(f"Total task types: {total}")
        print(f"Within tolerance (±{self.tolerance_percent}%): {within_tolerance}")
        print(f"Regressions (>{self.tolerance_percent}%): {regressions}")
        print(f"Improvements (<-{self.tolerance_percent}%): {improvements}")
        print()

        # Detailed results
        print("Task Type Details:")
        print("-" * 80)

        for result in results:
            status = "✅" if result.within_tolerance else "❌"

            if result.delta_percent > self.tolerance_percent:
                status = "🔴"  # Regression
            elif result.delta_percent < -self.tolerance_percent:
                status = "🟢"  # Improvement

            print(f"{status} {result.task_type}")
            print("  P95 Latency:")
            print(f"    Baseline: {result.baseline_p95:>10.2f} ms")
            print(f"    Current:  {result.current_p95:>10.2f} ms")
            print(f"    Delta:    {result.delta_ms:>+10.2f} ms ({result.delta_percent:>+6.2f}%)")
            print("  Memory:")
            print(f"    Baseline: {result.baseline_memory:>10.2f} MB")
            print(f"    Current:  {result.current_memory:>10.2f} MB")
            print(f"    Delta:    {result.memory_delta_percent:>+10.2f}%")
            print()

        print("=" * 80 + "\n")

    def generate_report(
        self,
        results: list[ComparisonResult],
        output_path: str,
    ) -> None:
        """Generate markdown comparison report."""
        with open(output_path, "w") as f:
            f.write("# Baseline Comparison Report\n\n")

            # Summary
            total = len(results)
            within_tolerance = sum(1 for r in results if r.within_tolerance)
            regressions = sum(1 for r in results if r.delta_percent > self.tolerance_percent)
            improvements = sum(1 for r in results if r.delta_percent < -self.tolerance_percent)

            f.write("## Summary\n\n")
            f.write(f"**Total Task Types**: {total}\n")
            f.write(f"**Within Tolerance (±{self.tolerance_percent}%)**: {within_tolerance}\n")
            f.write(f"**Regressions**: {regressions}\n")
            f.write(f"**Improvements**: {improvements}\n\n")

            if regressions > 0:
                f.write("⚠️ **Performance regressions detected**\n\n")
            else:
                f.write("✅ **All metrics within acceptable tolerance**\n\n")

            # Detailed table
            f.write("## Detailed Comparison\n\n")
            f.write("| Task Type | Baseline P95 (ms) | Current P95 (ms) | Delta | % Change | Status |\n")
            f.write("|-----------|-------------------|------------------|-------|----------|--------|\n")

            for result in results:
                status = "✅ OK" if result.within_tolerance else "❌ FAIL"

                if result.delta_percent > self.tolerance_percent:
                    status = "🔴 REGRESSION"
                elif result.delta_percent < -self.tolerance_percent:
                    status = "🟢 IMPROVED"

                f.write(
                    f"| {result.task_type} | {result.baseline_p95:.2f} | "
                    f"{result.current_p95:.2f} | {result.delta_ms:+.2f} | "
                    f"{result.delta_percent:+.2f}% | {status} |\n"
                )

            f.write("\n## Memory Comparison\n\n")
            f.write("| Task Type | Baseline (MB) | Current (MB) | % Change |\n")
            f.write("|-----------|---------------|--------------|----------|\n")

            for result in results:
                f.write(
                    f"| {result.task_type} | {result.baseline_memory:.2f} | "
                    f"{result.current_memory:.2f} | {result.memory_delta_percent:+.2f}% |\n"
                )

            f.write("\n## Recommendations\n\n")

            if regressions > 0:
                f.write("### Action Required\n\n")
                f.write("The following task types show performance regressions:\n\n")

                for result in results:
                    if result.delta_percent > self.tolerance_percent:
                        f.write(
                            f"- **{result.task_type}**: +{result.delta_percent:.2f}% " f"({result.delta_ms:+.2f} ms)\n"
                        )

                f.write("\n**Next Steps**:\n")
                f.write("1. Profile the regressed operations\n")
                f.write("2. Identify root cause of performance degradation\n")
                f.write("3. Optimize or revert changes\n")
                f.write("4. Re-run baseline comparison\n\n")
            else:
                f.write("### All Clear\n\n")
                f.write("All task types are within acceptable performance tolerance.\n")
                f.write("Refactoring has not caused performance regressions.\n\n")


def main():
    parser = argparse.ArgumentParser(description="Compare baseline performance measurements")
    parser.add_argument(
        "--baseline",
        required=True,
        help="Path to baseline aggregated metrics JSON",
    )
    parser.add_argument(
        "--current",
        required=True,
        help="Path to current aggregated metrics JSON",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=5.0,
        help="Acceptable tolerance percentage (default: 5.0)",
    )
    parser.add_argument(
        "--output",
        help="Output path for comparison report (markdown)",
    )

    args = parser.parse_args()

    comparator = BaselineComparator(tolerance_percent=args.tolerance)

    try:
        results = comparator.compare(args.baseline, args.current)
        comparator.print_summary(results)

        if args.output:
            comparator.generate_report(results, args.output)
            print(f"Report written to: {args.output}")

        # Exit with error code if regressions detected
        regressions = sum(1 for r in results if r.delta_percent > args.tolerance)
        if regressions > 0:
            sys.exit(1)

    except Exception as exc:
        print(f"Comparison failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
