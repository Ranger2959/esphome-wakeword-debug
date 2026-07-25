#!/usr/bin/with-contenv bashio

set -e

if [ ! -f /data/options.json ]; then
    exec python3 -m uvicorn app.main:app \
        --host "${HOST:-0.0.0.0}" \
        --port "${PORT:-8000}"
fi

export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
export OUTPUT_DIR="${OUTPUT_DIR:-/data/audio_clips}"
export UDP_HOST="${UDP_HOST:-0.0.0.0}"
export UDP_PORT="${UDP_PORT:-6056}"

export BUFFER_DURATION_SECONDS="$(bashio::config 'buffer_duration_seconds')"
export PRE_WAKE_DURATION_SECONDS="$(bashio::config 'pre_wake_duration_seconds')"
export POST_WAKE_DURATION_SECONDS="$(bashio::config 'post_wake_duration_seconds')"
export UDP_ENABLED="$(bashio::config 'udp_enabled')"
export UDP_ASSISTANT_ID="$(bashio::config 'udp_assistant_id')"
export UDP_SAMPLE_RATE="$(bashio::config 'udp_sample_rate')"
export UDP_SAMPLE_WIDTH="$(bashio::config 'udp_sample_width')"
export UDP_CHANNELS="$(bashio::config 'udp_channels')"

export MQTT_BROKER="$(bashio::config 'mqtt_broker')"
export MQTT_PORT="$(bashio::config 'mqtt_port')"
export MQTT_USERNAME="$(bashio::config 'mqtt_username')"
export MQTT_PASSWORD="$(bashio::config 'mqtt_password')"
export MQTT_TOPIC_PREFIX="$(bashio::config 'mqtt_topic_prefix')"
export MQTT_AUDIO_TOPIC="$(bashio::config 'mqtt_audio_topic')"
export MQTT_EVENT_TOPIC="$(bashio::config 'mqtt_event_topic')"
export MQTT_AUDIO_INFO_TOPIC="$(bashio::config 'mqtt_audio_info_topic')"
export MQTT_ENABLED="false"

if bashio::services.available mqtt; then
    export MQTT_ENABLED="true"
    export MQTT_BROKER="$(bashio::services mqtt host)"
    export MQTT_PORT="$(bashio::services mqtt port)"
    export MQTT_USERNAME="$(bashio::services mqtt username)"
    export MQTT_PASSWORD="$(bashio::services mqtt password)"
elif bashio::var.has_value "${MQTT_BROKER}"; then
    export MQTT_ENABLED="true"
fi

bashio::log.info "Starting Wake Word Debug Pipeline"
exec python3 -m uvicorn app.main:app --host "${HOST}" --port "${PORT}"
