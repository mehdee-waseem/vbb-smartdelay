-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- STOPS table - Berlin transit stops
CREATE TABLE IF NOT EXISTS stops (
    stop_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vbb_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL,
    geom GEOMETRY(Point, 4326) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index for fast radius searches
CREATE INDEX IF NOT EXISTS idx_stops_geom ON stops USING GIST(geom);

-- VEHICLE_POSITIONS table - raw vehicle data from VBB
CREATE TABLE IF NOT EXISTS vehicle_positions (
    vehicle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stop_id UUID REFERENCES stops(stop_id),
    trip_id VARCHAR(100) NOT NULL,
    line_name VARCHAR(20) NOT NULL,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL,
    delay_seconds INT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vehicle_positions_line ON vehicle_positions(line_name);
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_trip ON vehicle_positions(trip_id);

-- WEATHER_SNAPSHOTS table - live weather data
CREATE TABLE IF NOT EXISTS weather_snapshots (
    weather_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    temp_c DECIMAL(5, 2),
    rain_1h DECIMAL(5, 2),
    wind_speed_ms DECIMAL(5, 2),
    humidity_pct INT,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DELAY_EVENTS table - core prediction results
CREATE TABLE IF NOT EXISTS delay_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id UUID REFERENCES vehicle_positions(vehicle_id),
    stop_id UUID REFERENCES stops(stop_id),
    weather_id UUID REFERENCES weather_snapshots(weather_id),
    raw_delay_sec INT NOT NULL,
    weather_modifier DECIMAL(5, 2),
    predicted_delay_sec INT,
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_delay_events_stop ON delay_events(stop_id);
CREATE INDEX IF NOT EXISTS idx_delay_events_timestamp ON delay_events(event_timestamp DESC);

-- BIKES_AVAILABLE table - current bike locations
CREATE TABLE IF NOT EXISTS bikes_available (
    bike_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stop_id UUID REFERENCES stops(stop_id),
    nextbike_id VARCHAR(100) UNIQUE NOT NULL,
    lat DECIMAL(10, 8) NOT NULL,
    lon DECIMAL(11, 8) NOT NULL,
    is_reserved BOOLEAN DEFAULT FALSE,
    geom GEOMETRY(Point, 4326) NOT NULL,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bikes_geom ON bikes_available USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_bikes_reserved ON bikes_available(is_reserved);

-- Insert sample stops for testing (we'll populate this properly later)
INSERT INTO stops (vbb_id, name, lat, lon, geom) VALUES
    ('900100003', 'S+U Alexanderplatz Bhf', 52.521508, 13.411267, ST_GeomFromText('POINT(13.411267 52.521508)', 4326)),
    ('900096101', 'S+U Wittenau', 52.596451, 13.335524, ST_GeomFromText('POINT(13.335524 52.596451)', 4326)),
    ('900056105', 'U Friedrichstraße', 52.520008, 13.386389, ST_GeomFromText('POINT(13.386389 52.520008)', 4326))
ON CONFLICT (vbb_id) DO NOTHING;

COMMIT;
