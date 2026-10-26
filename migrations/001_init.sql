PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS species (
    species_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS images (
    image_id INTEGER PRIMARY KEY,
    species_id INTEGER REFERENCES species(species_id) ON DELETE RESTRICT,
    original_path TEXT NOT NULL,
    processed_path TEXT NOT NULL,
    width INTEGER NOT NULL CHECK (width = 512),
    height INTEGER NOT NULL CHECK (height = 512),
    channels INTEGER NOT NULL CHECK (channels = 3),
    original_sha256 TEXT NOT NULL UNIQUE CHECK (length(original_sha256) = 64),
    processed_sha256 TEXT NOT NULL CHECK (length(processed_sha256) = 64),
    source_url TEXT,
    license_note TEXT,
    split TEXT NOT NULL CHECK (split IN ('gallery', 'validation', 'test')),
    group_id TEXT NOT NULL,
    crop_json TEXT NOT NULL,
    preprocess_version TEXT NOT NULL,
    quality_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (quality_status IN ('pending', 'approved', 'rejected')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    review_note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feature_configs (
    config_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    feature_type TEXT NOT NULL CHECK (feature_type IN ('HOG', 'SPATIAL_HSV', 'ROOTSIFT_VLAD', 'GABOR')),
    dimension INTEGER NOT NULL CHECK (dimension > 0),
    parameters_json TEXT NOT NULL,
    preprocess_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS image_features (
    image_id INTEGER NOT NULL REFERENCES images(image_id) ON DELETE RESTRICT,
    config_id INTEGER NOT NULL REFERENCES feature_configs(config_id) ON DELETE RESTRICT,
    vector_json TEXT NOT NULL,
    vector_norm REAL NOT NULL CHECK (vector_norm >= 0),
    warning TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (image_id, config_id)
);

CREATE TABLE IF NOT EXISTS search_queries (
    query_id INTEGER PRIMARY KEY,
    query_path TEXT NOT NULL,
    query_sha256 TEXT NOT NULL CHECK (length(query_sha256) = 64),
    search_config_json TEXT NOT NULL,
    candidate_count INTEGER NOT NULL CHECK (candidate_count >= 5),
    duration_ms REAL NOT NULL CHECK (duration_ms >= 0),
    timings_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_results (
    query_id INTEGER NOT NULL REFERENCES search_queries(query_id) ON DELETE CASCADE,
    rank INTEGER NOT NULL CHECK (rank BETWEEN 1 AND 5),
    image_id INTEGER NOT NULL REFERENCES images(image_id) ON DELETE RESTRICT,
    scores_json TEXT NOT NULL CHECK (json_valid(scores_json)),
    total_score REAL NOT NULL CHECK (total_score BETWEEN 0 AND 1),
    PRIMARY KEY (query_id, rank),
    UNIQUE (query_id, image_id)
);

CREATE INDEX IF NOT EXISTS idx_images_gallery ON images(split, active, quality_status);
CREATE INDEX IF NOT EXISTS idx_images_species ON images(species_id);
CREATE INDEX IF NOT EXISTS idx_images_processed_hash ON images(processed_sha256);
CREATE INDEX IF NOT EXISTS idx_images_group ON images(group_id);
CREATE INDEX IF NOT EXISTS idx_features_config ON image_features(config_id, image_id);
CREATE INDEX IF NOT EXISTS idx_queries_time ON search_queries(created_at);

INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);


-- Cache invalidation for edits, including in-place vector updates.
CREATE TABLE IF NOT EXISTS gallery_revision (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    revision INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO gallery_revision(singleton, revision) VALUES (1, 0);

CREATE TRIGGER IF NOT EXISTS revision_images_insert
AFTER INSERT ON images
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_images_update
AFTER UPDATE ON images
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_images_delete
AFTER DELETE ON images
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_image_features_insert
AFTER INSERT ON image_features
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_image_features_update
AFTER UPDATE ON image_features
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_image_features_delete
AFTER DELETE ON image_features
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_feature_configs_insert
AFTER INSERT ON feature_configs
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_feature_configs_update
AFTER UPDATE ON feature_configs
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_feature_configs_delete
AFTER DELETE ON feature_configs
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_species_insert
AFTER INSERT ON species
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_species_update
AFTER UPDATE ON species
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;

CREATE TRIGGER IF NOT EXISTS revision_species_delete
AFTER DELETE ON species
BEGIN
    UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
END;
