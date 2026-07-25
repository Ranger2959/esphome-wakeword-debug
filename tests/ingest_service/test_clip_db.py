"""Tests for clip_db module."""
import tempfile
from pathlib import Path
import pytest

from ingest_service.app import clip_db


@pytest.fixture
def temp_db_path():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    yield db_path
    if db_path.exists():
        db_path.unlink()


def test_init_db(temp_db_path):
    """Test database initialization."""
    clip_db.init_db(temp_db_path)
    assert temp_db_path.exists()


def test_insert_clip(temp_db_path):
    """Test inserting a clip."""
    clip_db.init_db(temp_db_path)
    
    clip_id = clip_db.insert_clip(
        temp_db_path,
        filename="test.wav",
        timestamp="2024-01-01T00:00:00Z",
        assistant_id="test_assistant",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_UNKNOWN,
    )
    
    assert clip_id > 0
    
    # Verify the clip was inserted
    row = clip_db.get_clip(temp_db_path, clip_id)
    assert row is not None
    assert row["filename"] == "test.wav"
    assert row["label"] == clip_db.LABEL_UNKNOWN


def test_new_labels(temp_db_path):
    """Test new label types."""
    clip_db.init_db(temp_db_path)
    
    # Test False Negative label
    clip_id1 = clip_db.insert_clip(
        temp_db_path,
        filename="false_negative.wav",
        timestamp="2024-01-01T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_FALSE_NEGATIVE,
    )
    
    row1 = clip_db.get_clip(temp_db_path, clip_id1)
    assert row1["label"] == clip_db.LABEL_FALSE_NEGATIVE
    
    # Test Background Noise label
    clip_id2 = clip_db.insert_clip(
        temp_db_path,
        filename="background_noise.wav",
        timestamp="2024-01-01T00:01:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_BACKGROUND_NOISE,
    )
    
    row2 = clip_db.get_clip(temp_db_path, clip_id2)
    assert row2["label"] == clip_db.LABEL_BACKGROUND_NOISE


def test_update_label(temp_db_path):
    """Test updating a clip's label."""
    clip_db.init_db(temp_db_path)
    
    clip_id = clip_db.insert_clip(
        temp_db_path,
        filename="test.wav",
        timestamp="2024-01-01T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_UNKNOWN,
    )
    
    # Update to False Negative
    success = clip_db.update_label(temp_db_path, clip_id, clip_db.LABEL_FALSE_NEGATIVE)
    assert success
    
    row = clip_db.get_clip(temp_db_path, clip_id)
    assert row["label"] == clip_db.LABEL_FALSE_NEGATIVE
    
    # Update to Background Noise
    success = clip_db.update_label(temp_db_path, clip_id, clip_db.LABEL_BACKGROUND_NOISE)
    assert success
    
    row = clip_db.get_clip(temp_db_path, clip_id)
    assert row["label"] == clip_db.LABEL_BACKGROUND_NOISE


def test_soft_delete(temp_db_path):
    """Test soft-deleting a clip."""
    clip_db.init_db(temp_db_path)
    
    clip_id = clip_db.insert_clip(
        temp_db_path,
        filename="test.wav",
        timestamp="2024-01-01T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
    )
    
    # Verify clip is not deleted
    row = clip_db.get_clip(temp_db_path, clip_id)
    assert row["deleted"] == 0
    
    # Soft delete the clip
    success = clip_db.soft_delete_clip(temp_db_path, clip_id)
    assert success
    
    # Verify clip is marked as deleted
    row = clip_db.get_clip(temp_db_path, clip_id)
    assert row["deleted"] == 1


def test_undelete(temp_db_path):
    """Test restoring a soft-deleted clip."""
    clip_db.init_db(temp_db_path)
    
    clip_id = clip_db.insert_clip(
        temp_db_path,
        filename="test.wav",
        timestamp="2024-01-01T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
    )
    
    # Soft delete the clip
    clip_db.soft_delete_clip(temp_db_path, clip_id)
    
    # Restore the clip
    success = clip_db.undelete_clip(temp_db_path, clip_id)
    assert success
    
    # Verify clip is no longer deleted
    row = clip_db.get_clip(temp_db_path, clip_id)
    assert row["deleted"] == 0


def test_list_clips_exclude_deleted(temp_db_path):
    """Test that deleted clips are excluded by default."""
    clip_db.init_db(temp_db_path)
    
    # Insert a regular clip
    clip_id1 = clip_db.insert_clip(
        temp_db_path,
        filename="test1.wav",
        timestamp="2024-01-01T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
    )
    
    # Insert and delete another clip
    clip_id2 = clip_db.insert_clip(
        temp_db_path,
        filename="test2.wav",
        timestamp="2024-01-01T00:01:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
    )
    clip_db.soft_delete_clip(temp_db_path, clip_id2)
    
    # List clips without including deleted
    clips = clip_db.list_clips(temp_db_path, include_deleted=False)
    assert len(clips) == 1
    assert clips[0]["id"] == clip_id1


def test_list_clips_include_deleted(temp_db_path):
    """Test that deleted clips can be included."""
    clip_db.init_db(temp_db_path)
    
    # Insert a regular clip
    clip_id1 = clip_db.insert_clip(
        temp_db_path,
        filename="test1.wav",
        timestamp="2024-01-01T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
    )
    
    # Insert and delete another clip
    clip_id2 = clip_db.insert_clip(
        temp_db_path,
        filename="test2.wav",
        timestamp="2024-01-01T00:01:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
    )
    clip_db.soft_delete_clip(temp_db_path, clip_id2)
    
    # List clips including deleted
    clips = clip_db.list_clips(temp_db_path, include_deleted=True)
    assert len(clips) == 2
    returned_ids = {clip["id"] for clip in clips}
    assert returned_ids == {clip_id1, clip_id2}


def test_list_clips_filter_by_label(temp_db_path):
    """Test filtering clips by label."""
    clip_db.init_db(temp_db_path)
    
    # Insert clips with different labels
    clip_db.insert_clip(
        temp_db_path,
        filename="positive.wav",
        timestamp="2024-01-01T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_POSITIVE,
    )
    
    clip_db.insert_clip(
        temp_db_path,
        filename="false_negative.wav",
        timestamp="2024-01-01T00:01:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_FALSE_NEGATIVE,
    )
    
    clip_db.insert_clip(
        temp_db_path,
        filename="background_noise.wav",
        timestamp="2024-01-01T00:02:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_BACKGROUND_NOISE,
    )
    
    # Filter by False Negative
    clips = clip_db.list_clips(temp_db_path, label=clip_db.LABEL_FALSE_NEGATIVE)
    assert len(clips) == 1
    assert clips[0]["label"] == clip_db.LABEL_FALSE_NEGATIVE
    
    # Filter by Background Noise
    clips = clip_db.list_clips(temp_db_path, label=clip_db.LABEL_BACKGROUND_NOISE)
    assert len(clips) == 1
    assert clips[0]["label"] == clip_db.LABEL_BACKGROUND_NOISE


def _insert_numbered_clips(db_path, count, label=clip_db.LABEL_UNKNOWN):
    """Insert `count` clips with ascending timestamps; returns ids in insert order."""
    ids = []
    for index in range(count):
        ids.append(
            clip_db.insert_clip(
                db_path,
                filename=f"clip_{index:03d}.wav",
                timestamp=f"2024-01-01T00:{index:02d}:00Z",
                assistant_id="test",
                duration=5.0,
                sample_rate=48000,
                label=label,
            )
        )
    return ids


def test_list_clips_limit_and_offset(temp_db_path):
    """Test that limit and offset page through newest-first results."""
    clip_db.init_db(temp_db_path)
    _insert_numbered_clips(temp_db_path, 25)

    first_page = clip_db.list_clips(temp_db_path, limit=9, offset=0)
    assert len(first_page) == 9
    # Newest first: clip_024 down to clip_016.
    assert first_page[0]["filename"] == "clip_024.wav"
    assert first_page[-1]["filename"] == "clip_016.wav"

    second_page = clip_db.list_clips(temp_db_path, limit=9, offset=9)
    assert len(second_page) == 9
    assert second_page[0]["filename"] == "clip_015.wav"

    # Last page is partial.
    third_page = clip_db.list_clips(temp_db_path, limit=9, offset=18)
    assert len(third_page) == 7
    assert third_page[-1]["filename"] == "clip_000.wav"

    # Pages must not overlap.
    all_ids = [row["id"] for row in first_page + second_page + third_page]
    assert len(set(all_ids)) == 25


def test_list_clips_offset_past_end_returns_empty(temp_db_path):
    """Test that an offset beyond the result set yields no rows."""
    clip_db.init_db(temp_db_path)
    _insert_numbered_clips(temp_db_path, 5)

    clips = clip_db.list_clips(temp_db_path, limit=9, offset=90)
    assert clips == []


def test_list_clips_offset_without_limit(temp_db_path):
    """Test that offset works when no limit is supplied."""
    clip_db.init_db(temp_db_path)
    _insert_numbered_clips(temp_db_path, 5)

    clips = clip_db.list_clips(temp_db_path, offset=2)
    assert len(clips) == 3
    assert clips[0]["filename"] == "clip_002.wav"


def test_list_clips_unpaginated_by_default(temp_db_path):
    """Test that omitting limit returns every matching clip."""
    clip_db.init_db(temp_db_path)
    _insert_numbered_clips(temp_db_path, 12)

    clips = clip_db.list_clips(temp_db_path)
    assert len(clips) == 12


def test_count_clips_respects_filters(temp_db_path):
    """Test that count_clips applies the same filters as list_clips."""
    clip_db.init_db(temp_db_path)
    _insert_numbered_clips(temp_db_path, 10)

    clip_db.insert_clip(
        temp_db_path,
        filename="positive.wav",
        timestamp="2024-01-02T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_POSITIVE,
    )
    deleted_id = clip_db.insert_clip(
        temp_db_path,
        filename="gone.wav",
        timestamp="2024-01-03T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
    )
    clip_db.soft_delete_clip(temp_db_path, deleted_id)

    assert clip_db.count_clips(temp_db_path) == 11
    assert clip_db.count_clips(temp_db_path, include_deleted=True) == 12
    assert clip_db.count_clips(temp_db_path, label=clip_db.LABEL_POSITIVE) == 1
    assert (
        clip_db.count_clips(temp_db_path, start="2024-01-02T00:00:00Z") == 1
    )


def test_count_clips_unlabeled_only(temp_db_path):
    """Test that unlabeled_only counts Unknown/empty labels."""
    clip_db.init_db(temp_db_path)
    _insert_numbered_clips(temp_db_path, 4)
    clip_db.insert_clip(
        temp_db_path,
        filename="labeled.wav",
        timestamp="2024-01-02T00:00:00Z",
        assistant_id="test",
        duration=5.0,
        sample_rate=48000,
        label=clip_db.LABEL_POSITIVE,
    )

    assert clip_db.count_clips(temp_db_path) == 5
    assert clip_db.count_clips(temp_db_path, unlabeled_only=True) == 4
    assert (
        clip_db.count_clips(
            temp_db_path, label=clip_db.LABEL_POSITIVE, unlabeled_only=True
        )
        == 0
    )
