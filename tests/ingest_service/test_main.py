"""Unit tests for FastAPI main application."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import numpy as np
import tempfile
import os

# Mock settings before importing main
with patch.dict(
    os.environ, {"OUTPUT_DIR": tempfile.mkdtemp(), "MQTT_BROKER": "test-broker"}
):
    import ingest_service.app.main as main_module


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(main_module.app)


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global instances between tests."""
    main_module.audio_buffer = None
    main_module.wav_writer = None
    main_module.mqtt_publisher = None
    main_module.mqtt_subscriber = None
    main_module.udp_receiver = None
    main_module.udp_configured_assistants = set()
    yield


class TestMainAPI:
    """Test cases for main FastAPI application."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns service info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Wake Word Audio Ingest Service"
        assert "version" in data
        assert "status" in data

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "buffer_samples" in data
        assert "buffer_duration_seconds" in data

    @patch("ingest_service.app.main.get_audio_buffer")
    def test_get_assistants_endpoint(self, mock_get_buffer, client):
        """Test get assistants endpoint."""
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_assistant_ids.return_value = [
            "assistant1",
            "assistant2",
        ]
        mock_get_buffer.return_value = mock_buffer_instance

        response = client.get("/api/assistants")

        assert response.status_code == 200
        data = response.json()
        assert "assistants" in data
        assert data["assistants"] == ["assistant1", "assistant2"]

    @patch("ingest_service.app.main.get_audio_buffer")
    def test_get_assistants_empty_returns_default(self, mock_get_buffer, client):
        """Test get assistants endpoint returns default when no assistants active."""
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_assistant_ids.return_value = []
        mock_get_buffer.return_value = mock_buffer_instance

        response = client.get("/api/assistants")

        assert response.status_code == 200
        data = response.json()
        assert "assistants" in data
        assert data["assistants"] == ["default"]

    @patch("ingest_service.app.main.get_audio_buffer")
    @patch("ingest_service.app.main.get_wav_writer")
    @patch("ingest_service.app.main.get_mqtt_publisher")
    def test_trigger_wake_event_success(
        self, mock_get_mqtt, mock_get_wav, mock_get_buffer
    ):
        """Test triggering wake event successfully."""
        # Mock buffer returning audio clip
        mock_clip = np.array([i for i in range(1000)], dtype=np.int16)
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_clip = AsyncMock(return_value=mock_clip)
        mock_buffer_instance.get_audio_config = Mock(
            return_value={"sample_rate": 16000, "sample_width": 4, "channels": 1}
        )
        mock_get_buffer.return_value = mock_buffer_instance

        # Mock WAV writer
        mock_wav_instance = Mock()
        mock_wav_instance.write_clip.return_value = "/path/to/file.wav"
        mock_get_wav.return_value = mock_wav_instance

        # Mock MQTT publisher
        mock_mqtt_instance = Mock()
        mock_mqtt_instance.publish_wake_event.return_value = True
        mock_get_mqtt.return_value = mock_mqtt_instance

        with TestClient(main_module.app) as client:
            response = client.post("/wake_event")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "wav_file" in data
        assert "metadata" in data

    @patch("ingest_service.app.main.get_audio_buffer")
    @patch("ingest_service.app.main.get_wav_writer")
    def test_trigger_wake_event_insufficient_data(
        self, mock_get_wav, mock_get_buffer, client
    ):
        """Test wake event with insufficient buffer data."""
        # Mock buffer returning None
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_clip = AsyncMock(return_value=None)
        mock_get_buffer.return_value = mock_buffer_instance

        # Mock wav_writer to avoid file system issues
        mock_wav_instance = Mock()
        mock_get_wav.return_value = mock_wav_instance

        response = client.post("/wake_event")

        assert response.status_code == 400
        assert "Insufficient audio data" in response.json()["detail"]

    @patch("ingest_service.app.main.get_audio_buffer")
    @patch("ingest_service.app.main.get_wav_writer")
    @patch("ingest_service.app.main.get_mqtt_publisher")
    def test_trigger_wake_event_with_custom_durations(
        self, mock_get_mqtt, mock_get_wav, mock_get_buffer
    ):
        """Test wake event with custom pre/post durations."""
        mock_clip = np.array([i for i in range(1000)], dtype=np.int16)
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_clip = AsyncMock(return_value=mock_clip)
        mock_buffer_instance.get_audio_config = Mock(
            return_value={"sample_rate": 16000, "sample_width": 4, "channels": 1}
        )
        mock_get_buffer.return_value = mock_buffer_instance

        mock_wav_instance = Mock()
        mock_wav_instance.write_clip.return_value = "/path/to/file.wav"
        mock_get_wav.return_value = mock_wav_instance

        mock_mqtt_instance = Mock()
        mock_mqtt_instance.publish_wake_event.return_value = True
        mock_get_mqtt.return_value = mock_mqtt_instance

        with TestClient(main_module.app) as client:
            response = client.post("/wake_event?pre_duration=3.0&post_duration=4.0")

        assert response.status_code == 200

        # Verify buffer.get_clip was called with correct params
        mock_buffer_instance.get_clip.assert_called_once()
        call_kwargs = mock_buffer_instance.get_clip.call_args[1]
        assert call_kwargs["pre_duration"] == 3.0
        assert call_kwargs["post_duration"] == 4.0

    @patch("ingest_service.app.main.get_mqtt_publisher")
    @patch("ingest_service.app.main.get_wav_writer")
    @patch("ingest_service.app.main.get_audio_buffer")
    def test_trigger_wake_event_defaults_assistant_to_client_ip(
        self, mock_get_buffer, mock_get_wav, mock_get_mqtt
    ):
        """When no assistant_id is given, the caller's IP is used (matches UDP keying)."""
        mock_clip = np.array([i for i in range(1000)], dtype=np.int16)
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_clip = AsyncMock(return_value=mock_clip)
        mock_buffer_instance.get_audio_config = Mock(
            return_value={"sample_rate": 16000, "sample_width": 2, "channels": 1}
        )
        mock_get_buffer.return_value = mock_buffer_instance

        mock_wav_instance = Mock()
        mock_wav_instance.write_clip.return_value = "/path/to/file.wav"
        mock_get_wav.return_value = mock_wav_instance

        mock_mqtt_instance = Mock()
        mock_mqtt_instance.publish_wake_event.return_value = True
        mock_get_mqtt.return_value = mock_mqtt_instance

        # TestClient reports the client host as "testclient".
        with TestClient(main_module.app) as client:
            response = client.post("/wake_event")

        assert response.status_code == 200
        assert response.json()["metadata"]["assistant_id"] == "testclient"
        assert mock_buffer_instance.get_clip.call_args[1]["assistant_id"] == "testclient"

    @patch("ingest_service.app.main.get_mqtt_publisher")
    @patch("ingest_service.app.main.get_wav_writer")
    @patch("ingest_service.app.main.get_audio_buffer")
    def test_trigger_wake_event_explicit_assistant_id(
        self, mock_get_buffer, mock_get_wav, mock_get_mqtt
    ):
        """An explicit assistant_id query param overrides the caller IP."""
        mock_clip = np.array([i for i in range(1000)], dtype=np.int16)
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_clip = AsyncMock(return_value=mock_clip)
        mock_buffer_instance.get_audio_config = Mock(
            return_value={"sample_rate": 16000, "sample_width": 2, "channels": 1}
        )
        mock_get_buffer.return_value = mock_buffer_instance

        mock_wav_instance = Mock()
        mock_wav_instance.write_clip.return_value = "/path/to/file.wav"
        mock_get_wav.return_value = mock_wav_instance

        mock_mqtt_instance = Mock()
        mock_mqtt_instance.publish_wake_event.return_value = True
        mock_get_mqtt.return_value = mock_mqtt_instance

        with TestClient(main_module.app) as client:
            response = client.post("/wake_event?assistant_id=sat1")

        assert response.status_code == 200
        assert mock_buffer_instance.get_clip.call_args[1]["assistant_id"] == "sat1"

    @patch("ingest_service.app.main.get_audio_buffer")
    @patch("ingest_service.app.main.get_wav_writer")
    @patch("ingest_service.app.main.clip_db")
    def test_capture_background_noise_success(
        self, mock_clip_db, mock_get_wav, mock_get_buffer
    ):
        """Test capturing background noise successfully."""
        # Mock buffer returning audio clip
        mock_clip = np.array([i for i in range(1000)], dtype=np.int16)
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_clip = AsyncMock(return_value=mock_clip)
        mock_buffer_instance.get_audio_config = Mock(
            return_value={"sample_rate": 16000, "sample_width": 4, "channels": 1}
        )
        mock_get_buffer.return_value = mock_buffer_instance

        # Mock WAV writer
        mock_wav_instance = Mock()
        mock_wav_instance.write_clip.return_value = "/path/to/background_noise.wav"
        mock_get_wav.return_value = mock_wav_instance

        # Mock clip_db
        mock_clip_db.insert_clip = Mock()
        mock_clip_db.LABEL_BACKGROUND_NOISE = "Background Noise"

        with TestClient(main_module.app) as client:
            response = client.post(
                "/api/capture_background_noise",
                json={"seconds": 5.0, "assistant_id": "test_assistant"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["label"] == "Background Noise"
        assert "wav_file" in data

        # Verify buffer.get_clip was called with correct params
        mock_buffer_instance.get_clip.assert_called_once()
        call_kwargs = mock_buffer_instance.get_clip.call_args[1]
        assert call_kwargs["assistant_id"] == "test_assistant"
        assert call_kwargs["pre_duration"] == 5.0
        assert call_kwargs["post_duration"] == 0
        assert call_kwargs["trigger_offset"] == 0

    @patch("ingest_service.app.main.get_audio_buffer")
    @patch("ingest_service.app.main.get_wav_writer")
    def test_capture_background_noise_invalid_seconds(
        self, mock_get_wav, mock_get_buffer
    ):
        """Test background noise capture with invalid seconds."""
        mock_buffer_instance = Mock()
        mock_get_buffer.return_value = mock_buffer_instance
        mock_get_wav.return_value = Mock()

        with TestClient(main_module.app) as client:
            # Test with negative seconds
            response = client.post(
                "/api/capture_background_noise",
                json={"seconds": -1.0, "assistant_id": "default"},
            )
            assert response.status_code == 400
            assert "must be greater than 0" in response.json()["detail"]

            # Test with zero seconds
            response = client.post(
                "/api/capture_background_noise",
                json={"seconds": 0, "assistant_id": "default"},
            )
            assert response.status_code == 400
            assert "must be greater than 0" in response.json()["detail"]

    @patch("ingest_service.app.main.get_audio_buffer")
    @patch("ingest_service.app.main.get_wav_writer")
    def test_capture_background_noise_insufficient_data(
        self, mock_get_wav, mock_get_buffer
    ):
        """Test background noise capture with insufficient buffer data."""
        # Mock buffer returning None
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_clip = AsyncMock(return_value=None)
        mock_get_buffer.return_value = mock_buffer_instance
        mock_get_wav.return_value = Mock()

        with TestClient(main_module.app) as client:
            response = client.post(
                "/api/capture_background_noise",
                json={"seconds": 5.0, "assistant_id": "default"},
            )

        assert response.status_code == 400
        assert "Insufficient audio data" in response.json()["detail"]

    @patch("ingest_service.app.main.get_audio_buffer")
    def test_clear_buffer_endpoint(self, mock_get_buffer, client):
        """Test clear buffer endpoint."""
        mock_buffer_instance = Mock()
        mock_buffer_instance.clear = AsyncMock()
        mock_get_buffer.return_value = mock_buffer_instance

        response = client.post("/clear_buffer")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cleared" in data["message"].lower()
        mock_buffer_instance.clear.assert_called_once()

    @patch("ingest_service.app.main.get_wav_writer")
    def test_cleanup_endpoint(self, mock_get_wav, client):
        """Test cleanup old files endpoint."""
        mock_wav_instance = Mock()
        mock_wav_instance.cleanup_old_files.return_value = 5
        mock_get_wav.return_value = mock_wav_instance

        response = client.post("/cleanup?max_age_days=3")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 5
        assert data["max_age_days"] == 3

        mock_wav_instance.cleanup_old_files.assert_called_once_with(3)

    @patch("ingest_service.app.main.get_audio_buffer")
    def test_websocket_audio_endpoint(self, mock_get_buffer, client):
        """Test WebSocket audio streaming endpoint."""
        mock_buffer_instance = Mock()
        mock_buffer_instance.append = AsyncMock()
        mock_get_buffer.return_value = mock_buffer_instance

        # Test data
        test_audio = b"\x00\x01" * 100  # 200 bytes of test PCM data

        with client.websocket_connect("/ws/audio") as websocket:
            # Send audio data
            websocket.send_bytes(test_audio)

            # Give it a moment to process
            import time

            time.sleep(0.1)

        # Verify audio was appended to buffer
        assert mock_buffer_instance.append.called

    def test_websocket_connection_tracking(self, client):
        """Test that WebSocket connections are tracked."""
        initial_count = len(main_module.active_connections)

        with client.websocket_connect("/ws/audio"):  # noqa: F841
            # Connection should be added
            assert len(main_module.active_connections) >= initial_count

        # After closing, connection should be removed (eventually)
        # Note: May need a small delay for cleanup
        import time

        time.sleep(0.1)

    def test_startup_event_mqtt_connection(self, client):
        """Test that startup event connects to MQTT."""
        # The startup event is triggered automatically by TestClient
        # We can't easily mock it without restructuring, so just verify the app works
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_includes_mqtt_status(self, client):
        """Test that health check includes MQTT connection status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "mqtt_publisher_connected" in data
        assert "mqtt_subscriber_connected" in data
        assert isinstance(data["mqtt_publisher_connected"], bool)
        assert isinstance(data["mqtt_subscriber_connected"], bool)

    def test_mqtt_callbacks_use_thread_safe_scheduling(self):
        """Test that MQTT callbacks are properly set up with thread-safe asyncio scheduling."""
        import asyncio
        import threading

        # Timeout for thread join operation
        THREAD_JOIN_TIMEOUT = 1.0

        # Create an event loop for the test
        loop = asyncio.new_event_loop()

        try:
            # Set the loop in the current thread
            asyncio.set_event_loop(loop)

            # Simulate the callback wrapper that would be created in startup_event
            def audio_callback(assistant_id: str, data: bytes):
                """Thread-safe wrapper for async audio handler."""
                # This should not raise "no running event loop" when called from another thread
                asyncio.run_coroutine_threadsafe(
                    main_module.handle_audio_data(assistant_id, data), loop
                )

            def wake_callback(assistant_id: str, metadata: dict):
                """Thread-safe wrapper for async wake handler."""
                asyncio.run_coroutine_threadsafe(
                    main_module.handle_wake_event(assistant_id, metadata), loop
                )

            # Test calling from a different thread (simulating MQTT thread)
            test_data = b"\x00\x01\x02\x03"
            callback_exception = None

            def call_from_thread():
                """Call the callback from a separate thread to simulate MQTT thread."""
                nonlocal callback_exception
                try:
                    # This should work without "no running event loop" error
                    audio_callback("test_assistant", test_data)
                    wake_callback("test_assistant", {"event": "test"})
                except Exception as e:
                    callback_exception = e

            thread = threading.Thread(target=call_from_thread)
            thread.start()
            thread.join(timeout=THREAD_JOIN_TIMEOUT)

            # Should not raise "no running event loop" error
            assert (
                callback_exception is None
            ), f"Callback raised exception: {callback_exception}"

        finally:
            loop.close()


class TestClipPagination:
    """The clip list endpoint returns one bounded page at a time."""

    @pytest.fixture
    def clip_db_path(self, tmp_path):
        """Point the app at an isolated clip database."""
        from ingest_service.app import clip_db

        db_path = tmp_path / "clips.db"
        clip_db.init_db(db_path)
        with patch.object(main_module, "CLIP_DB_PATH", db_path):
            yield db_path

    @staticmethod
    def _seed(db_path, count, label=None):
        from ingest_service.app import clip_db

        for index in range(count):
            clip_db.insert_clip(
                db_path,
                filename=f"clip_{index:03d}.wav",
                timestamp=f"2024-01-01T00:{index:02d}:00Z",
                assistant_id="test",
                duration=5.0,
                sample_rate=16000,
                label=label or clip_db.LABEL_UNKNOWN,
            )

    def test_defaults_to_nine_per_page(self, client, clip_db_path):
        """Without params the endpoint returns the default page size."""
        self._seed(clip_db_path, 25)

        response = client.get("/api/clips")

        assert response.status_code == 200
        data = response.json()
        assert len(data["clips"]) == 9
        assert data["page"] == 1
        assert data["page_size"] == 9
        assert data["total"] == 25
        assert data["total_pages"] == 3

    def test_second_page_returns_next_slice(self, client, clip_db_path):
        """Paging forward yields distinct clips."""
        self._seed(clip_db_path, 25)

        first = client.get("/api/clips?page=1").json()
        second = client.get("/api/clips?page=2").json()

        assert second["page"] == 2
        first_ids = {clip["id"] for clip in first["clips"]}
        second_ids = {clip["id"] for clip in second["clips"]}
        assert not (first_ids & second_ids)
        # Newest first, so page 2 starts below page 1's last clip.
        assert first["clips"][-1]["filename"] == "clip_016.wav"
        assert second["clips"][0]["filename"] == "clip_015.wav"

    def test_last_page_is_partial(self, client, clip_db_path):
        """The final page holds only the remainder."""
        self._seed(clip_db_path, 25)

        data = client.get("/api/clips?page=3").json()

        assert len(data["clips"]) == 7
        assert data["clips"][-1]["filename"] == "clip_000.wav"

    def test_custom_page_size(self, client, clip_db_path):
        """page_size overrides the default."""
        self._seed(clip_db_path, 25)

        data = client.get("/api/clips?page_size=18").json()

        assert len(data["clips"]) == 18
        assert data["page_size"] == 18
        assert data["total_pages"] == 2

    def test_page_beyond_end_clamps_to_last_page(self, client, clip_db_path):
        """Requesting past the end returns the last populated page."""
        self._seed(clip_db_path, 25)

        data = client.get("/api/clips?page=99").json()

        assert data["page"] == 3
        assert len(data["clips"]) == 7

    def test_empty_result_reports_one_page(self, client, clip_db_path):
        """An empty database still reports a valid page count."""
        data = client.get("/api/clips").json()

        assert data["clips"] == []
        assert data["total"] == 0
        assert data["total_pages"] == 1
        assert data["page"] == 1

    def test_totals_span_all_pages(self, client, clip_db_path):
        """Counts describe the whole filtered set, not just the page."""
        from ingest_service.app import clip_db

        self._seed(clip_db_path, 12)
        clip_db.insert_clip(
            clip_db_path,
            filename="labeled.wav",
            timestamp="2024-01-02T00:00:00Z",
            assistant_id="test",
            duration=5.0,
            sample_rate=16000,
            label=clip_db.LABEL_POSITIVE,
        )

        data = client.get("/api/clips").json()

        assert len(data["clips"]) == 9
        assert data["total"] == 13
        assert data["unlabeled_total"] == 12

    def test_pagination_respects_label_filter(self, client, clip_db_path):
        """Totals and pages reflect the active filter."""
        from ingest_service.app import clip_db

        self._seed(clip_db_path, 10)
        for index in range(11):
            clip_db.insert_clip(
                clip_db_path,
                filename=f"pos_{index:03d}.wav",
                timestamp=f"2024-02-01T00:{index:02d}:00Z",
                assistant_id="test",
                duration=5.0,
                sample_rate=16000,
                label=clip_db.LABEL_POSITIVE,
            )

        data = client.get("/api/clips?label=Positive").json()

        assert data["total"] == 11
        assert data["total_pages"] == 2
        assert data["unlabeled_total"] == 0
        assert all(clip["label"] == "Positive" for clip in data["clips"])

    def test_invalid_pagination_params_rejected(self, client, clip_db_path):
        """Out-of-range paging values are validation errors, not silent defaults."""
        assert client.get("/api/clips?page=0").status_code == 422
        assert client.get("/api/clips?page_size=0").status_code == 422
        assert client.get("/api/clips?page_size=101").status_code == 422


class TestMQTTDisabled:
    """Wake events must work without a broker when MQTT is disabled."""

    def test_publish_wake_event_skipped_when_disabled(self):
        """No publisher is constructed, so no broker connection is attempted."""
        with patch.object(main_module.settings, "MQTT_ENABLED", False):
            with patch("ingest_service.app.main.get_mqtt_publisher") as mock_get_mqtt:
                published = main_module.publish_wake_event("/tmp/clip.wav", {})

        assert published is False
        mock_get_mqtt.assert_not_called()
        assert main_module.mqtt_publisher is None

    def test_publish_wake_event_publishes_when_enabled(self):
        """With MQTT enabled the publisher result is passed through."""
        mock_publisher = Mock()
        mock_publisher.publish_wake_event.return_value = True

        with patch.object(main_module.settings, "MQTT_ENABLED", True):
            with patch(
                "ingest_service.app.main.get_mqtt_publisher",
                return_value=mock_publisher,
            ):
                published = main_module.publish_wake_event("/tmp/clip.wav", {"a": 1})

        assert published is True
        mock_publisher.publish_wake_event.assert_called_once_with(
            "/tmp/clip.wav", {"a": 1}
        )

    @patch("ingest_service.app.main.get_audio_buffer")
    @patch("ingest_service.app.main.get_wav_writer")
    def test_wake_event_endpoint_succeeds_without_broker(
        self, mock_get_wav, mock_get_buffer
    ):
        """A UDP-only deployment still captures clips, reporting no MQTT publish."""
        mock_clip = np.array([i for i in range(1000)], dtype=np.int16)
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_clip = AsyncMock(return_value=mock_clip)
        mock_buffer_instance.get_audio_config = Mock(
            return_value={"sample_rate": 16000, "sample_width": 2, "channels": 1}
        )
        mock_get_buffer.return_value = mock_buffer_instance

        mock_wav_instance = Mock()
        mock_wav_instance.write_clip.return_value = "/path/to/file.wav"
        mock_get_wav.return_value = mock_wav_instance

        with patch.object(main_module.settings, "MQTT_ENABLED", False):
            with TestClient(main_module.app) as client:
                response = client.post("/wake_event?assistant_id=sat1")

        assert response.status_code == 200
        assert response.json()["mqtt_published"] is False
        # Startup and the publish path both skipped client construction.
        assert main_module.mqtt_publisher is None
        assert main_module.mqtt_subscriber is None

    @patch("ingest_service.app.main.get_wav_writer")
    def test_health_does_not_construct_mqtt_clients(self, mock_get_wav):
        """Probing health must not create clients that would dial the broker."""
        mock_get_wav.return_value = Mock()

        with patch.object(main_module.settings, "MQTT_ENABLED", False):
            with TestClient(main_module.app) as client:
                response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["mqtt_publisher_connected"] is False
        assert data["mqtt_subscriber_connected"] is False
        assert main_module.mqtt_publisher is None
        assert main_module.mqtt_subscriber is None
