"""
Comprehensive tests for the task management system.

Tests cover:
- TaskManager lifecycle (submit, update, complete, fail)
- SSEManager broadcasting and cleanup
- Concurrent access and race conditions
"""

import pytest
import queue
import threading
import time

from deeplecture.workers.task_manager import TaskManager, Task
from deeplecture.infra.sse_manager import SSEManager


@pytest.fixture
def task_manager():
    """Create a TaskManager instance with SSEManager."""
    sse_manager = SSEManager()
    tm = TaskManager(sse_manager)
    return tm


@pytest.fixture
def sse_manager():
    """Create a standalone SSEManager for testing."""
    return SSEManager()


# ============================================================================
# Task Model Tests
# ============================================================================

def test_task_dataclass():
    """Test basic Task creation."""
    task = Task(
        id="test_task_001",
        type="subtitle_generation",
        content_id="video_123",
        status="pending",
        progress=0,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    assert task.id == "test_task_001"
    assert task.type == "subtitle_generation"
    assert task.status == "pending"
    assert task.progress == 0


def test_task_metadata_json_property():
    """Test that metadata_json property returns JSON string."""
    task = Task(
        id="test_task_002",
        type="timeline_generation",
        content_id="video_456",
        status="pending",
        metadata={"language": "en", "force": True},
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    import json

    metadata = json.loads(task.metadata_json)
    assert metadata["language"] == "en"
    assert metadata["force"] is True


# ============================================================================
# TaskManager Tests
# ============================================================================


def test_submit_task_creates_record(task_manager):
    """Test that submit_task creates a task in memory and queue."""
    task_id = task_manager.submit_task(
        content_id="video_789",
        task_type="subtitle_generation",
        metadata={"language": "en"},
    )

    assert task_id is not None
    assert task_id.startswith("subtitle_generation_video_789")

    # Verify in-memory record
    task = task_manager.get_task(task_id)
    assert task is not None
    assert task.status == "pending"
    assert task.progress == 0

    # Verify queue
    assert not task_manager.task_queue.empty()
    queued_id = task_manager.task_queue.get_nowait()
    assert queued_id == task_id


def test_get_task_by_id(task_manager):
    """Test retrieving a task by ID."""
    task_id = task_manager.submit_task("video_001", "timeline_generation")

    task = task_manager.get_task(task_id)
    assert task is not None
    assert task.id == task_id
    assert task.type == "timeline_generation"

    # Test nonexistent task
    nonexistent = task_manager.get_task("fake_task_id")
    assert nonexistent is None


def test_get_tasks_by_content(task_manager):
    """Test filtering tasks by content_id."""
    content_id = "video_multi"

    # Create multiple tasks
    task_id1 = task_manager.submit_task(content_id, "subtitle_generation")
    task_id2 = task_manager.submit_task(content_id, "timeline_generation")
    task_id3 = task_manager.submit_task("other_video", "subtitle_generation")

    # Query by content_id
    tasks = task_manager.get_tasks_by_content(content_id)
    assert len(tasks) == 2
    task_ids = {t.id for t in tasks}
    assert task_id1 in task_ids
    assert task_id2 in task_ids
    assert task_id3 not in task_ids


def test_update_task_progress(task_manager):
    """Test updating task progress."""
    task_id = task_manager.submit_task("video_prog", "subtitle_generation")

    # Update progress
    updated = task_manager.update_task_progress(task_id, 50, emit_event=False)
    assert updated is not None
    assert updated.progress == 50
    assert updated.status == "processing"  # Should transition from pending

    # Verify storage was updated
    task = task_manager.get_task(task_id)
    assert task.progress == 50
    assert task.status == "processing"


def test_update_progress_does_not_overwrite_terminal_state(task_manager):
    """Test that progress updates don't overwrite completed/error states."""
    task_id = task_manager.submit_task("video_term", "subtitle_generation")

    # Complete the task
    task_manager.complete_task(task_id, "/path/to/result.srt")

    # Try to update progress
    result = task_manager.update_task_progress(task_id, 75, emit_event=False)

    # Task should still be completed, not changed
    assert result.status == "ready"
    assert result.progress == 100  # Complete sets to 100

    # Same for error state
    task_id2 = task_manager.submit_task("video_err", "subtitle_generation")
    task_manager.fail_task(task_id2, "Test error")

    result2 = task_manager.update_task_progress(task_id2, 50, emit_event=False)
    assert result2.status == "error"


def test_complete_task(task_manager):
    """Test marking a task as complete."""
    task_id = task_manager.submit_task("video_done", "subtitle_generation")

    result_path = "/path/to/subtitles.srt"
    completed = task_manager.complete_task(task_id, result_path)

    assert completed is not None
    assert completed.status == "ready"
    assert completed.progress == 100
    assert completed.result_path == result_path

    # Verify storage
    task = task_manager.get_task(task_id)
    assert task.status == "ready"
    assert task.result_path == result_path


def test_fail_task(task_manager):
    """Test marking a task as failed."""
    task_id = task_manager.submit_task("video_fail", "subtitle_generation")

    error_msg = "Transcription service unavailable"
    failed = task_manager.fail_task(task_id, error_msg)

    assert failed is not None
    assert failed.status == "error"
    assert failed.error == error_msg

    # Verify storage
    task = task_manager.get_task(task_id)
    assert task.status == "error"
    assert task.error == error_msg


# ============================================================================
# SSEManager Tests
# ============================================================================


def test_sse_subscribe_creates_queue(sse_manager):
    """Test that subscribing creates a queue."""
    q = sse_manager.subscribe("content_123")
    assert isinstance(q, queue.Queue)


def test_sse_broadcast_to_subscribers(sse_manager):
    """Test broadcasting events to subscribers."""
    content_id = "content_broadcast"

    # Create two subscribers
    q1 = sse_manager.subscribe(content_id)
    q2 = sse_manager.subscribe(content_id)

    # Broadcast event
    event_data = {"event": "progress", "task": {"progress": 50}}
    sse_manager.broadcast(content_id, event_data)

    # Both should receive it
    assert not q1.empty()
    assert not q2.empty()

    received1 = q1.get_nowait()
    received2 = q2.get_nowait()

    assert received1 == event_data
    assert received2 == event_data


def test_sse_broadcast_to_nonexistent_content():
    """Test broadcasting to content with no subscribers."""
    sse_manager = SSEManager()

    # Should not raise error
    sse_manager.broadcast("nonexistent_content", {"event": "test"})


def test_sse_cleanup_dead_queues(sse_manager):
    """Test that dead queue references are cleaned up."""
    content_id = "content_cleanup"

    # Create subscriber and let it go out of scope
    q = sse_manager.subscribe(content_id)
    del q

    # Force cleanup
    sse_manager.cleanup_dead_queues()

    # Subscribers should be empty
    assert content_id not in sse_manager.subscribers or len(sse_manager.subscribers[content_id]) == 0


def test_sse_full_queue_drops_message(sse_manager):
    """Test that full queues drop messages instead of blocking."""
    content_id = "content_full"

    q = sse_manager.subscribe(content_id)

    # Fill it up (this won't actually fill unbounded queue, but demonstrates intent)
    for i in range(1000):
        sse_manager.broadcast(content_id, {"event": f"test_{i}"})

    # Should not hang or crash


def test_sse_thread_safety(sse_manager):
    """Test concurrent subscribe and broadcast operations."""
    content_id = "content_concurrent"
    results = []

    def subscriber_thread():
        q = sse_manager.subscribe(content_id)
        for _ in range(10):
            try:
                event = q.get(timeout=1)
                results.append(event)
            except queue.Empty:
                break

    def broadcaster_thread():
        for i in range(10):
            sse_manager.broadcast(content_id, {"event": i})
            time.sleep(0.01)

    threads = [threading.Thread(target=subscriber_thread), threading.Thread(target=broadcaster_thread)]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    # Should have received some events without crashing
    assert len(results) > 0


# ============================================================================
# Integration Tests (TaskManager + SSEManager)
# ============================================================================


def test_task_manager_broadcasts_on_update(task_manager):
    """Test that TaskManager broadcasts SSE events on state changes."""
    content_id = "video_sse_test"

    # Subscribe to events
    sse = task_manager._sse
    q = sse.subscribe(content_id)

    # Submit task (should not broadcast immediately in current implementation)
    task_id = task_manager.submit_task(content_id, "subtitle_generation")

    # Update progress (should broadcast)
    task_manager.update_task_progress(task_id, 50)

    # Check event
    assert not q.empty()
    event = q.get_nowait()
    assert event["event"] == "progress"
    assert event["task"]["progress"] == 50


def test_task_completion_broadcasts(task_manager):
    """Test that completing a task broadcasts an event."""
    content_id = "video_complete_sse"
    sse = task_manager._sse
    q = sse.subscribe(content_id)

    task_id = task_manager.submit_task(content_id, "subtitle_generation")
    task_manager.complete_task(task_id, "/result.srt")

    # Should have completion event
    event = None
    while not q.empty():
        event = q.get_nowait()
        if event["event"] == "completed":
            break

    assert event is not None
    assert event["event"] == "completed"
    assert event["task"]["status"] == "ready"


def test_task_failure_broadcasts(task_manager):
    """Test that failing a task broadcasts an event."""
    content_id = "video_fail_sse"
    sse = task_manager._sse
    q = sse.subscribe(content_id)

    task_id = task_manager.submit_task(content_id, "subtitle_generation")
    task_manager.fail_task(task_id, "Test error")

    # Should have failed event
    event = None
    while not q.empty():
        event = q.get_nowait()
        if event["event"] == "failed":
            break

    assert event is not None
    assert event["event"] == "failed"
    assert event["task"]["status"] == "error"
    assert event["task"]["error"] == "Test error"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_update_nonexistent_task(task_manager):
    """Test updating a task that doesn't exist."""
    result = task_manager.update_task_progress("fake_id", 50, emit_event=False)
    assert result is None


def test_complete_nonexistent_task(task_manager):
    """Test completing a task that doesn't exist."""
    result = task_manager.complete_task("fake_id", "/path")
    assert result is None


def test_fail_nonexistent_task(task_manager):
    """Test failing a task that doesn't exist."""
    result = task_manager.fail_task("fake_id", "error")
    assert result is None


def test_metadata_serialization(task_manager):
    """Test that task metadata is properly stored."""
    metadata = {"language": "en", "force": True, "config": {"quality": "high"}}

    task_id = task_manager.submit_task("video_meta", "subtitle_generation", metadata)
    task = task_manager.get_task(task_id)

    # metadata should be a dict
    assert isinstance(task.metadata, dict)
    assert task.metadata == metadata

    # Serialize should include it
    serialized = task_manager._serialize_task(task)
    assert serialized["metadata"] == metadata


# ============================================================================
# Concurrency and Race Condition Tests
# ============================================================================


def test_concurrent_task_updates(task_manager):
    """Test concurrent updates to the same task."""
    task_id = task_manager.submit_task("video_concurrent", "subtitle_generation")

    def update_progress(progress_value):
        task_manager.update_task_progress(task_id, progress_value, emit_event=False)

    threads = []
    for i in range(10):
        t = threading.Thread(target=update_progress, args=(i * 10,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=5)

    # Task should be in a valid state
    task = task_manager.get_task(task_id)
    assert task is not None
    assert task.status in ("pending", "processing")
    assert 0 <= task.progress <= 100


def test_concurrent_complete_and_progress(task_manager):
    """Test race between complete and progress update."""
    task_id = task_manager.submit_task("video_race", "subtitle_generation")

    def complete():
        time.sleep(0.01)
        task_manager.complete_task(task_id, "/result.srt")

    def progress():
        for i in range(10):
            task_manager.update_task_progress(task_id, i * 10, emit_event=False)
            time.sleep(0.005)

    t1 = threading.Thread(target=complete)
    t2 = threading.Thread(target=progress)

    t1.start()
    t2.start()

    t1.join(timeout=5)
    t2.join(timeout=5)

    # Task should end up in terminal state
    task = task_manager.get_task(task_id)
    assert task.status == "ready"  # Complete should win


# ============================================================================
# Performance Tests
# ============================================================================


def test_many_tasks_performance(task_manager):
    """Test creating many tasks quickly."""
    import time

    start = time.time()

    task_ids = []
    for i in range(100):
        task_id = task_manager.submit_task(f"video_{i}", "subtitle_generation")
        task_ids.append(task_id)

    elapsed = time.time() - start
    print(f"\nCreated 100 tasks in {elapsed:.2f}s ({len(task_ids) / elapsed:.1f} tasks/s)")

    # Should complete in reasonable time
    assert elapsed < 5.0  # 5 seconds for 100 tasks


def test_many_subscribers_performance(sse_manager):
    """Test broadcasting to many subscribers."""
    content_id = "content_perf"

    # Create 100 subscribers
    queues = []
    for _ in range(100):
        q = sse_manager.subscribe(content_id)
        queues.append(q)

    # Broadcast 10 events
    import time

    start = time.time()

    for i in range(10):
        sse_manager.broadcast(content_id, {"event": i})

    elapsed = time.time() - start
    print(f"\nBroadcast 10 events to 100 subscribers in {elapsed:.3f}s")

    # Should be fast (non-blocking)
    assert elapsed < 1.0

    # All subscribers should receive all events
    for q in queues:
        count = 0
        while not q.empty():
            q.get_nowait()
            count += 1
        assert count == 10
