-- Requires foreign_keys OFF before BEGIN; Repository restores it after commit.
-- Rebuild only Images; preserve IDs, vectors, history and all references.
CREATE TABLE images_new (
    image_id INTEGER PRIMARY KEY,
    species_id INTEGER REFERENCES species(species_id) ON DELETE RESTRICT,
    original_path TEXT NOT NULL,
    processed_path TEXT NOT NULL,
    width INTEGER NOT NULL CHECK (width IN (128, 512)),
    height INTEGER NOT NULL CHECK (height = width),
    channels INTEGER NOT NULL CHECK (channels = 3),
    original_sha256 TEXT NOT NULL UNIQUE CHECK (length(original_sha256) = 64),
    processed_sha256 TEXT NOT NULL CHECK (length(processed_sha256) = 64),
    source_url TEXT,
    license_note TEXT,
    split TEXT NOT NULL CHECK (split IN ('gallery', 'validation', 'test')),
    group_id TEXT NOT NULL,
    crop_json TEXT NOT NULL,
    preprocess_version TEXT NOT NULL,
    quality_status TEXT NOT NULL DEFAULT 'pending' CHECK (quality_status IN ('pending', 'approved', 'rejected')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    review_note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO images_new SELECT * FROM images;
DROP TABLE images;
ALTER TABLE images_new RENAME TO images;

CREATE INDEX idx_images_gallery ON images(split, active, quality_status);
CREATE INDEX idx_images_species ON images(species_id);
CREATE INDEX idx_images_processed_hash ON images(processed_sha256);
CREATE INDEX idx_images_group ON images(group_id);

CREATE TRIGGER revision_images_insert AFTER INSERT ON images
BEGIN UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER revision_images_update AFTER UPDATE ON images
BEGIN UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1; END;
CREATE TRIGGER revision_images_delete AFTER DELETE ON images
BEGIN UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1; END;
UPDATE gallery_revision SET revision = revision + 1 WHERE singleton = 1;
