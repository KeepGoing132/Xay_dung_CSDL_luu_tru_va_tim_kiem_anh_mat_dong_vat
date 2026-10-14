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
