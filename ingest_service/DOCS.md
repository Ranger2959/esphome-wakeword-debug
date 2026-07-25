# Wake Word Debug Pipeline

Capture, review, and label wake word audio sent by ESPHome devices.

## Setup

1. Install and start the add-on.
2. Point the ESPHome `wake_audio_stream` component at the Home Assistant host IP and UDP port `6056`.
3. Open the add-on Web UI and enable **Show in sidebar** if desired.

For UDP-only installations, MQTT is optional. The add-on automatically uses credentials from the Home Assistant Mosquitto service when it is available; otherwise, configure an external broker. Leaving the broker blank disables MQTT.

## ESPHome

```yaml
wake_audio_stream:
  id: wake_audio_streamer
  ip_address: 192.168.1.100  # Home Assistant host IP
  port: 6056
  buffer_duration: 500ms
```

The device must also call the add-on's `POST /wake_event` endpoint when a wake word is detected. Use `http://HOME_ASSISTANT_IP:8000/wake_event` when the default TCP port mapping is enabled. See the project README for assistant IDs, WWD2 packet framing, and complete examples.

## Storage

Clips, metadata, and the label database are stored in the add-on's persistent `/data` directory and included in cold backups.

## Options

- `buffer_duration_seconds`: Rolling audio retained per assistant.
- `pre_wake_duration_seconds`: Audio retained before each wake event.
- `post_wake_duration_seconds`: Audio retained after each wake event.
- `udp_enabled`: Enables UDP audio on port `6056`.
- `udp_assistant_id`: Optional fixed assistant ID for all UDP audio.
- `udp_sample_rate`, `udp_sample_width`, `udp_channels`: Fallback format for legacy raw or WWD1 packets. WWD2 packets carry their own format.
- `mqtt_*`: Broker credentials and MQTT topics. Mosquitto service credentials take precedence when available.
