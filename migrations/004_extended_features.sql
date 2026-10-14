-- Rebuild with foreign_keys OFF outside the transaction; retain IDs and references.
CREATE TABLE feature_configs_new (
    config_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    feature_type TEXT NOT NULL CHECK (feature_type IN ('HSV','HOG','LBP','SPATIAL_HSV','COLOR_MOMENTS','GLCM')),
    dimension INTEGER NOT NULL CHECK (dimension > 0),
    parameters_json TEXT NOT NULL,
    preprocess_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO feature_configs_new SELECT * FROM feature_configs;
DROP TABLE feature_configs;
ALTER TABLE feature_configs_new RENAME TO feature_configs;
CREATE TRIGGER revision_feature_configs_insert AFTER INSERT ON feature_configs
BEGIN UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER revision_feature_configs_update AFTER UPDATE ON feature_configs
BEGIN UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER revision_feature_configs_delete AFTER DELETE ON feature_configs
BEGIN UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1; END;
ALTER TABLE search_results ADD COLUMN extra_scores_json TEXT NOT NULL DEFAULT '{}';
UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
