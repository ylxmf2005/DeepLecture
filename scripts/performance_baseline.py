#!/usr/bin/env python3
"""
Performance baseline measurement script.

Runs all task types with instrumentation to establish baseline metrics.
This script ONLY measures performance - it does NOT modify business logic.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from deeplecture.performance import enable_profiling, get_profiler
from deeplecture.workers.worker import WorkerServices, dispatch_task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Test scenarios for each task type
TEST_SCENARIOS = {
    "subtitle_generation": [
        {
            "name": "short_video_2min",
            "metadata": {
                "content_id": "test_subtitle_short",
                "source_language": "en",
            },
            "description": "2-minute video subtitle generation",
        },
        {
            "name": "medium_video_10min",
            "metadata": {
                "content_id": "test_subtitle_medium",
                "source_language": "en",
            },
            "description": "10-minute video subtitle generation",
        },
        {
            "name": "long_video_30min",
            "metadata": {
                "content_id": "test_subtitle_long",
                "source_language": "en",
            },
            "description": "30-minute video subtitle generation",
        },
    ],
    "subtitle_enhancement": [
        {
            "name": "short_subtitle_enhance",
            "metadata": {
                "content_id": "test_enhance_short",
                "target_language": "zh",
            },
            "description": "2-minute subtitle enhancement",
        },
        {
            "name": "medium_subtitle_enhance",
            "metadata": {
                "content_id": "test_enhance_medium",
                "target_language": "zh",
            },
            "description": "10-minute subtitle enhancement",
        },
    ],
    "subtitle_translation": [
        {
            "name": "short_subtitle_translate",
            "metadata": {
                "content_id": "test_translate_short",
                "target_language": "zh",
            },
            "description": "2-minute subtitle translation",
        },
        {
            "name": "medium_subtitle_translate",
            "metadata": {
                "content_id": "test_translate_medium",
                "target_language": "zh",
            },
            "description": "10-minute subtitle translation",
        },
    ],
    "timeline_generation": [
        {
            "name": "timeline_short",
            "metadata": {
                "content_id": "test_timeline_short",
                "subtitle_path": "data/test/subtitles/short.srt",
                "language": "en",
                "learner_profile": "beginner",
            },
            "description": "Timeline generation for 2-minute video",
        },
        {
            "name": "timeline_medium",
            "metadata": {
                "content_id": "test_timeline_medium",
                "subtitle_path": "data/test/subtitles/medium.srt",
                "language": "en",
                "learner_profile": "intermediate",
            },
            "description": "Timeline generation for 10-minute video",
        },
    ],
    "video_generation": [
        {
            "name": "slide_5pages",
            "metadata": {
                "deck_id": "test_deck_5",
                "tts_language": "en",
                "page_break_silence_seconds": 1.0,
            },
            "description": "5-page slide deck video generation",
        },
        {
            "name": "slide_20pages",
            "metadata": {
                "deck_id": "test_deck_20",
                "tts_language": "en",
                "page_break_silence_seconds": 1.0,
            },
            "description": "20-page slide deck video generation",
        },
    ],
    "note_generation": [
        {
            "name": "note_short",
            "metadata": {
                "content_id": "test_note_short",
                "context_mode": "auto",
                "learner_profile": "beginner",
            },
            "description": "Note generation for 2-minute video",
        },
        {
            "name": "note_medium",
            "metadata": {
                "content_id": "test_note_medium",
                "context_mode": "auto",
                "learner_profile": "intermediate",
            },
            "description": "Note generation for 10-minute video",
        },
    ],
    "voiceover_generation": [
        {
            "name": "voiceover_short",
            "metadata": {
                "content_id": "test_voiceover_short",
                "language": "zh",
            },
            "description": "Voiceover generation for 2-minute video",
        },
        {
            "name": "voiceover_medium",
            "metadata": {
                "content_id": "test_voiceover_medium",
                "language": "zh",
            },
            "description": "Voiceover generation for 10-minute video",
        },
    ],
    "slide_explanation": [
        {
            "name": "explain_single_slide",
            "metadata": {
                "content_id": "test_explain",
                "image_path": "data/test/slides/slide1.png",
                "json_path": "data/test/explanations/slide1.json",
                "timestamp": 10.0,
                "raw_instruction": "Explain this concept",
            },
            "description": "Single slide explanation",
        },
    ],
    "video_import_url": [
        {
            "name": "import_youtube_short",
            "metadata": {
                "content_id": "test_import_short",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "custom_name": "Test Import",
            },
            "description": "Import short YouTube video",
        },
    ],
    "pdf_merge": [
        {
            "name": "merge_2pdfs",
            "metadata": {
                "content_id": "test_merge_2",
                "temp_dir": "/tmp/merge_test",
                "temp_paths": ["/tmp/file1.pdf", "/tmp/file2.pdf"],
                "display_name": "Merged PDF",
                "file_count": 2,
            },
            "description": "Merge 2 PDFs",
        },
        {
            "name": "merge_10pdfs",
            "metadata": {
                "content_id": "test_merge_10",
                "temp_dir": "/tmp/merge_test",
                "temp_paths": [f"/tmp/file{i}.pdf" for i in range(1, 11)],
                "display_name": "Merged PDF",
                "file_count": 10,
            },
            "description": "Merge 10 PDFs",
        },
    ],
    "video_merge": [
        {
            "name": "merge_2videos",
            "metadata": {
                "content_id": "test_video_merge_2",
                "temp_dir": "/tmp/video_merge_test",
                "temp_paths": ["/tmp/video1.mp4", "/tmp/video2.mp4"],
                "display_name": "Merged Video",
                "file_count": 2,
            },
            "description": "Merge 2 videos",
        },
        {
            "name": "merge_5videos",
            "metadata": {
                "content_id": "test_video_merge_5",
                "temp_dir": "/tmp/video_merge_test",
                "temp_paths": [f"/tmp/video{i}.mp4" for i in range(1, 6)],
                "display_name": "Merged Video",
                "file_count": 5,
            },
            "description": "Merge 5 videos",
        },
    ],
}


class BaselineRunner:
    """Runner for performance baseline tests."""

    def __init__(self, output_dir: str, dry_run: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dry_run = dry_run
        self.profiler = get_profiler()
        enable_profiling()

    def run_baseline_tests(
        self,
        task_types: list[str] | None = None,
        iterations: int = 3,
    ) -> None:
        """
        Run baseline tests for specified task types.

        Args:
            task_types: List of task types to test, or None for all
            iterations: Number of iterations per scenario for statistical significance
        """
        if task_types is None:
            task_types = list(TEST_SCENARIOS.keys())

        logger.info("Starting performance baseline tests")
        logger.info(f"Task types: {', '.join(task_types)}")
        logger.info(f"Iterations per scenario: {iterations}")
        logger.info(f"Dry run: {self.dry_run}")

        # Create services once (simulating worker thread behavior)
        services = WorkerServices.create() if not self.dry_run else None

        total_tests = sum(len(TEST_SCENARIOS.get(tt, [])) * iterations for tt in task_types)
        completed = 0

        for task_type in task_types:
            scenarios = TEST_SCENARIOS.get(task_type, [])
            if not scenarios:
                logger.warning(f"No test scenarios defined for {task_type}")
                continue

            logger.info(f"\n{'=' * 60}")
            logger.info(f"Testing: {task_type}")
            logger.info(f"Scenarios: {len(scenarios)}")
            logger.info(f"{'=' * 60}")

            for scenario in scenarios:
                scenario_name = scenario["name"]
                description = scenario["description"]
                metadata = scenario["metadata"]

                logger.info(f"\nScenario: {scenario_name}")
                logger.info(f"  Description: {description}")

                for iteration in range(iterations):
                    completed += 1
                    progress = (completed / total_tests) * 100

                    logger.info(f"  Iteration {iteration + 1}/{iterations} " f"(Overall progress: {progress:.1f}%)")

                    if self.dry_run:
                        logger.info("  [DRY RUN] Skipping actual execution")
                        continue

                    try:
                        # Measure operation with profiler
                        with self.profiler.measure(
                            task_type,
                            metadata={
                                "scenario": scenario_name,
                                "iteration": iteration + 1,
                                **metadata,
                            },
                        ):
                            result = dispatch_task(task_type, metadata, services)
                            logger.info(f"  Result: {result}")

                    except Exception as exc:
                        logger.error(
                            f"  Failed: {exc}",
                            exc_info=True,
                        )

        logger.info(f"\n{'=' * 60}")
        logger.info("Baseline tests completed")
        logger.info(f"{'=' * 60}\n")

    def generate_report(self) -> None:
        """Generate comprehensive baseline report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export raw metrics
        raw_path = self.output_dir / f"raw_metrics_{timestamp}.json"
        self.profiler.export_raw_metrics(str(raw_path))

        # Export aggregated metrics
        agg_path = self.output_dir / f"aggregated_metrics_{timestamp}.json"
        self.profiler.export_aggregated_metrics(str(agg_path))

        # Print summary
        self.profiler.print_summary()

        # Generate markdown report
        report_path = self.output_dir / f"baseline_report_{timestamp}.md"
        self._generate_markdown_report(report_path)

        logger.info("\nReports generated:")
        logger.info(f"  Raw metrics: {raw_path}")
        logger.info(f"  Aggregated:  {agg_path}")
        logger.info(f"  Report:      {report_path}")

    def _generate_markdown_report(self, output_path: Path) -> None:
        """Generate markdown format baseline report."""
        aggregated = self.profiler.get_aggregated_metrics()

        with open(output_path, "w") as f:
            f.write("# Performance Baseline Report\n\n")
            f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")

            f.write("## Executive Summary\n\n")
            f.write(f"Total operations measured: {sum(a.count for a in aggregated)}\n")
            f.write(f"Task types tested: {len(aggregated)}\n")
            f.write(
                f"Overall success rate: "
                f"{sum(a.success_count for a in aggregated) / sum(a.count for a in aggregated) * 100:.1f}%\n\n"
            )

            f.write("## Baseline Metrics by Task Type\n\n")

            for agg in aggregated:
                f.write(f"### {agg.operation_name}\n\n")
                f.write(f"**Samples**: {agg.count}\n\n")

                f.write("**Latency (ms)**:\n")
                f.write(f"- P50: {agg.p50_duration_ms:.2f}\n")
                f.write(f"- P95: {agg.p95_duration_ms:.2f}\n")
                f.write(f"- P99: {agg.p99_duration_ms:.2f}\n")
                f.write(f"- Avg: {agg.avg_duration_ms:.2f}\n")
                f.write(f"- Min: {agg.min_duration_ms:.2f}\n")
                f.write(f"- Max: {agg.max_duration_ms:.2f}\n\n")

                f.write("**Memory**:\n")
                f.write(f"- Avg Delta: {agg.avg_memory_delta_mb:.2f} MB\n\n")

                f.write("**Reliability**:\n")
                f.write(f"- Success Rate: {agg.success_rate:.1f}%\n")
                f.write(f"- Successes: {agg.success_count}\n")
                f.write(f"- Failures: {agg.failure_count}\n\n")

            f.write("## Performance Budget\n\n")
            f.write("Acceptable tolerance for refactor: **±5%**\n\n")

            f.write("| Task Type | P95 Baseline (ms) | Acceptable Range (ms) |\n")
            f.write("|-----------|-------------------|-----------------------|\n")

            for agg in aggregated:
                lower = agg.p95_duration_ms * 0.95
                upper = agg.p95_duration_ms * 1.05
                f.write(f"| {agg.operation_name} | {agg.p95_duration_ms:.2f} | " f"{lower:.2f} - {upper:.2f} |\n")

            f.write("\n## Monitoring Recommendations\n\n")
            f.write("1. **Track P95 latency** for all task types in production\n")
            f.write("2. **Alert on >5% degradation** from baseline\n")
            f.write("3. **Monitor memory growth** - alert on >10% increase\n")
            f.write("4. **Track error rates** - alert on <95% success rate\n")
            f.write("5. **Compare weekly** against baseline during refactor\n\n")

            f.write("## Next Steps\n\n")
            f.write("- [ ] Review baseline metrics with team\n")
            f.write("- [ ] Set up continuous monitoring dashboard\n")
            f.write("- [ ] Configure alerting thresholds\n")
            f.write("- [ ] Begin Phase 1 refactoring\n")


def main():
    parser = argparse.ArgumentParser(description="Run performance baseline measurements")
    parser.add_argument(
        "--output-dir",
        default="reports/performance",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--task-types",
        nargs="+",
        help="Specific task types to test (default: all)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of iterations per scenario",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - show scenarios without executing",
    )

    args = parser.parse_args()

    runner = BaselineRunner(
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )

    try:
        runner.run_baseline_tests(
            task_types=args.task_types,
            iterations=args.iterations,
        )

        if not args.dry_run:
            runner.generate_report()

    except KeyboardInterrupt:
        logger.info("\nBaseline tests interrupted by user")
        if not args.dry_run:
            logger.info("Generating partial report...")
            runner.generate_report()
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Baseline tests failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
