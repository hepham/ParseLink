-- ==================================================
-- DATABASE DESIGN FOR MOVIE WEBSITE WITH M3U8 LINKS AND TRANSCRIPTS
-- Updated Version with transcript_id support
-- ==================================================

-- 1. MOVIES TABLE
-- Stores basic movie information with tmdb_id and imdb_id
CREATE TABLE movies (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tmdb_id VARCHAR(20) NULL,
    imdb_id VARCHAR(20) NULL,
    title VARCHAR(500) NOT NULL,
    status ENUM('active', 'inactive', 'deleted') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_movie_ids CHECK (tmdb_id IS NOT NULL OR imdb_id IS NOT NULL),
    CONSTRAINT uk_movie_tmdb_imdb UNIQUE (tmdb_id, imdb_id)
);

-- 2. MOVIE_LINKS TABLE
-- Stores m3u8 master playlist links for each movie with transcript support
-- Each m3u8 is a master playlist containing multiple quality variants
CREATE TABLE movie_links (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    movie_id BIGINT NOT NULL,
    m3u8_url VARCHAR(2000) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    transcript_id VARCHAR(50) NULL, -- ID for subtitle/dialogue
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign key
    CONSTRAINT fk_movie_links_movie_id FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicate links (removed quality)
    CONSTRAINT uk_movie_link_unique UNIQUE (movie_id, m3u8_url)
);

-- 3. TRANSCRIPTS TABLE (Optional - for transcript ID reference)
-- Stores only transcript ID for external API calls
-- Actual transcript data is retrieved from external API server using this ID
CREATE TABLE transcripts (
    id VARCHAR(50) PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 4. PERFORMANCE INDEXES
-- Primary search indexes for movies
CREATE INDEX idx_movies_tmdb_id ON movies(tmdb_id);
CREATE INDEX idx_movies_imdb_id ON movies(imdb_id);
CREATE INDEX idx_movies_tmdb_imdb ON movies(tmdb_id, imdb_id);
CREATE INDEX idx_movies_status ON movies(status);
CREATE INDEX idx_movies_created_at ON movies(created_at);

-- Movie links indexes
CREATE INDEX idx_movie_links_movie_id ON movie_links(movie_id);

CREATE INDEX idx_movie_links_active ON movie_links(is_active);
CREATE INDEX idx_movie_links_transcript_id ON movie_links(transcript_id);
CREATE INDEX idx_movie_links_created_at ON movie_links(created_at);

-- Composite indexes for common queries
CREATE INDEX idx_movie_links_movie_active ON movie_links(movie_id, is_active);


-- ==================================================
-- SAMPLE QUERIES
-- ==================================================

-- 1. Query links by tmdb_id
SELECT 
    m.id as movie_id,
    m.title,
    m.tmdb_id,
    m.imdb_id,
    ml.id as link_id,
    ml.m3u8_url,
    ml.is_active,
    ml.transcript_id,
    ml.created_at
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
WHERE m.tmdb_id = '12345' 
  AND ml.is_active = TRUE
ORDER BY ml.created_at DESC;

-- 2. Query links by imdb_id
SELECT 
    m.id as movie_id,
    m.title,
    m.tmdb_id,
    m.imdb_id,
    ml.id as link_id,
    ml.m3u8_url,
    ml.is_active,
    ml.transcript_id,
    ml.created_at
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
WHERE m.imdb_id = 'tt1234567' 
  AND ml.is_active = TRUE
ORDER BY ml.created_at DESC;

-- 3. Query links by both tmdb_id and imdb_id (flexible search)
SELECT 
    m.id as movie_id,
    m.title,
    m.tmdb_id,
    m.imdb_id,
    ml.id as link_id,
    ml.m3u8_url,
    ml.is_active,
    ml.transcript_id,
    ml.created_at
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
WHERE (m.tmdb_id = '12345' OR m.imdb_id = 'tt1234567')
  AND ml.is_active = TRUE
ORDER BY ml.created_at DESC;

-- 4. Query links with transcript information
SELECT 
    m.title,
    ml.m3u8_url,
    ml.transcript_id,
    t.language as transcript_language,
    t.format as transcript_format,
    t.file_url as transcript_url
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
LEFT JOIN transcripts t ON ml.transcript_id = t.id
WHERE m.tmdb_id = '12345' 
  AND ml.is_active = TRUE
ORDER BY ml.created_at DESC;

-- 5. Query links with transcript language filter
SELECT 
    m.title,
    ml.m3u8_url,
    ml.transcript_id,
    ml.created_at,
    t.language as transcript_language
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
LEFT JOIN transcripts t ON ml.transcript_id = t.id
WHERE (m.tmdb_id = '12345' OR m.imdb_id = 'tt1234567')
  AND ml.is_active = TRUE
  AND t.language IN ('vi', 'en')
ORDER BY ml.created_at DESC;

-- 6. Insert or update movie (upsert pattern)
INSERT INTO movies (tmdb_id, imdb_id, title, original_title, release_year, overview)
VALUES ('12345', 'tt1234567', 'Movie Title', 'Original Title', 2023, 'Movie overview...')
ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    original_title = VALUES(original_title),
    release_year = VALUES(release_year),
    overview = VALUES(overview),
    updated_at = CURRENT_TIMESTAMP;

-- 7. Add new m3u8 master playlist link with transcript
INSERT INTO movie_links (movie_id, m3u8_url, transcript_id)
SELECT 
    m.id,
    'https://server1.com/movie.m3u8',
    'transcript_001'
FROM movies m
WHERE m.tmdb_id = '12345'
ON DUPLICATE KEY UPDATE
    m3u8_url = VALUES(m3u8_url),
    transcript_id = VALUES(transcript_id),
    updated_at = CURRENT_TIMESTAMP;

-- 8. Add transcript information
INSERT INTO transcripts (id, title, language, format, file_url)
VALUES ('transcript_001', 'Movie Subtitles Vietnamese', 'vi', 'srt', 'https://cdn.example.com/subtitles/movie_vi.srt')
ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    language = VALUES(language),
    format = VALUES(format),
    file_url = VALUES(file_url),
    updated_at = CURRENT_TIMESTAMP;

-- ==================================================
-- HELPER FUNCTIONS AND PROCEDURES
-- ==================================================

-- Function to find movie by either tmdb_id or imdb_id
DELIMITER //
CREATE FUNCTION get_movie_id(p_tmdb_id VARCHAR(20), p_imdb_id VARCHAR(20))
RETURNS BIGINT
READS SQL DATA
DETERMINISTIC
BEGIN
    DECLARE movie_id BIGINT DEFAULT NULL;
    
    SELECT id INTO movie_id
    FROM movies
    WHERE (p_tmdb_id IS NOT NULL AND tmdb_id = p_tmdb_id)
       OR (p_imdb_id IS NOT NULL AND imdb_id = p_imdb_id)
    LIMIT 1;
    
    RETURN movie_id;
END//
DELIMITER ;

-- Procedure to get movie links with transcript information
DELIMITER //
CREATE PROCEDURE get_movie_links_with_transcripts(
    IN p_tmdb_id VARCHAR(20),
    IN p_imdb_id VARCHAR(20),
    IN p_quality VARCHAR(20),
    IN p_transcript_language VARCHAR(10)
)
BEGIN
    SELECT 
        m.id as movie_id,
        m.title,
        m.tmdb_id,
        m.imdb_id,
        ml.id as link_id,
        ml.m3u8_url,
        ml.quality,
        ml.is_active,
        ml.transcript_id,
        ml.created_at,
        t.language as transcript_language,
        t.format as transcript_format,
        t.file_url as transcript_url
    FROM movies m
    JOIN movie_links ml ON m.id = ml.movie_id
    LEFT JOIN transcripts t ON ml.transcript_id = t.id
    WHERE (p_tmdb_id IS NULL OR m.tmdb_id = p_tmdb_id)
      AND (p_imdb_id IS NULL OR m.imdb_id = p_imdb_id)
      AND (p_quality IS NULL OR ml.quality = p_quality)
      AND (p_transcript_language IS NULL OR t.language = p_transcript_language)
      AND ml.is_active = TRUE
    ORDER BY 
        CASE ml.quality 
            WHEN '4K' THEN 1
            WHEN '1080p' THEN 2
            WHEN '720p' THEN 3
            WHEN '480p' THEN 4
            ELSE 5
        END;
END//
DELIMITER ;

-- ==================================================
-- VIEWS FOR COMMON QUERIES
-- ==================================================

-- View for active movie links with transcript ID reference
CREATE VIEW v_active_movie_links AS
SELECT 
    m.id as movie_id,
    m.tmdb_id,
    m.imdb_id,
    m.title,
    ml.id as link_id,
    ml.m3u8_url,
    ml.transcript_id,
    ml.created_at
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
LEFT JOIN transcripts t ON ml.transcript_id = t.id
WHERE ml.is_active = TRUE
  AND m.status = 'active';

-- View for movie statistics
CREATE VIEW v_movie_stats AS
SELECT 
    m.id,
    m.tmdb_id,
    m.imdb_id,
    m.title,
    COUNT(ml.id) as total_links,
    COUNT(CASE WHEN ml.is_active = TRUE THEN 1 END) as active_links,
    COUNT(CASE WHEN ml.transcript_id IS NOT NULL THEN 1 END) as links_with_transcripts,
    MAX(ml.created_at) as latest_link_added
FROM movies m
LEFT JOIN movie_links ml ON m.id = ml.movie_id
WHERE m.status = 'active'
GROUP BY m.id, m.tmdb_id, m.imdb_id, m.title;

-- ==================================================
-- PERFORMANCE OPTIMIZATIONS
-- ==================================================

-- 1. Partitioning for large datasets (optional)
-- ALTER TABLE movie_links PARTITION BY RANGE (YEAR(created_at)) (
--     PARTITION p2023 VALUES LESS THAN (2024),
--     PARTITION p2024 VALUES LESS THAN (2025),
--     PARTITION p_future VALUES LESS THAN MAXVALUE
-- );

-- 2. Full-text search index for movie titles
ALTER TABLE movies ADD FULLTEXT(title, original_title);

-- 3. Composite index for common filtering

CREATE INDEX idx_movie_links_active_created ON movie_links(is_active, created_at);

-- ==================================================
-- CACHING STRATEGIES
-- ==================================================

-- Example Redis cache keys structure:
-- movie_links:{tmdb_id}:{imdb_id}:{quality} -> JSON of links
-- movie_info:{tmdb_id}:{imdb_id} -> JSON of movie information
-- transcript:{transcript_id} -> JSON of transcript data

-- Cache invalidation triggers
DELIMITER //
CREATE TRIGGER invalidate_movie_cache_after_update
AFTER UPDATE ON movies
FOR EACH ROW
BEGIN
    -- Log cache invalidation (implement cache clearing in application)
    INSERT INTO cache_invalidation_log (table_name, record_id, action, timestamp)
    VALUES ('movies', NEW.id, 'UPDATE', NOW());
END//

CREATE TRIGGER invalidate_link_cache_after_insert
AFTER INSERT ON movie_links
FOR EACH ROW
BEGIN
    INSERT INTO cache_invalidation_log (table_name, record_id, action, timestamp)
    VALUES ('movie_links', NEW.id, 'INSERT', NOW());
END//

CREATE TRIGGER invalidate_link_cache_after_update
AFTER UPDATE ON movie_links
FOR EACH ROW
BEGIN
    INSERT INTO cache_invalidation_log (table_name, record_id, action, timestamp)
    VALUES ('movie_links', NEW.id, 'UPDATE', NOW());
END//
DELIMITER ;

-- Cache invalidation log table
CREATE TABLE cache_invalidation_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    table_name VARCHAR(50) NOT NULL,
    record_id BIGINT NOT NULL,
    action VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_cache_log_timestamp (timestamp),
    INDEX idx_cache_log_table (table_name)
);

-- ==================================================
-- MONITORING AND HEALTH CHECKS
-- ==================================================

-- Table for tracking link performance
CREATE TABLE link_performance_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    link_id BIGINT NOT NULL,
    response_time INT, -- milliseconds
    status_code INT,
    error_message TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_link_performance_link_id FOREIGN KEY (link_id) REFERENCES movie_links(id) ON DELETE CASCADE,
    
    INDEX idx_link_perf_link_id (link_id),
    INDEX idx_link_perf_checked_at (checked_at)
);

-- Procedure to check link health
DELIMITER //
CREATE PROCEDURE check_link_health(IN p_link_id BIGINT)
BEGIN
    DECLARE v_url VARCHAR(2000);
    
    SELECT m3u8_url INTO v_url FROM movie_links WHERE id = p_link_id;
    
    -- This would be called from application code to actually check the URL
    -- and insert results into link_performance_log
    SELECT CONCAT('Check URL: ', v_url) as message;
END//
DELIMITER ;

-- ==================================================
-- SAMPLE DATA INSERTION
-- ==================================================

-- Insert sample movies
INSERT INTO movies (tmdb_id, imdb_id, title, original_title, release_year, overview) VALUES
('12345', 'tt1234567', 'Avengers: Endgame', 'Avengers: Endgame', 2019, 'The epic conclusion to the Infinity Saga that has defined the Marvel Cinematic Universe...'),
('67890', 'tt7654321', 'Spider-Man: No Way Home', 'Spider-Man: No Way Home', 2021, 'Peter Parker seeks help from Doctor Strange when his identity is revealed...'),
('11111', NULL, 'The Batman', 'The Batman', 2022, 'In his second year of fighting crime, Batman uncovers corruption in Gotham City...');

-- Insert sample transcripts
INSERT INTO transcripts (id, title, language, format, file_url) VALUES
('transcript_001', 'Avengers Endgame Vietnamese Subtitles', 'vi', 'srt', 'https://cdn.example.com/subtitles/avengers_endgame_vi.srt'),
('transcript_002', 'Avengers Endgame English Subtitles', 'en', 'srt', 'https://cdn.example.com/subtitles/avengers_endgame_en.srt'),
('transcript_003', 'Spider-Man No Way Home Vietnamese Subtitles', 'vi', 'srt', 'https://cdn.example.com/subtitles/spiderman_nwh_vi.srt');

-- Insert sample movie links
INSERT INTO movie_links (movie_id, m3u8_url, quality, transcript_id) VALUES
(1, 'https://server1.com/avengers_endgame_1080p.m3u8', '1080p', 'transcript_001'),
(1, 'https://server1.com/avengers_endgame_720p.m3u8', '720p', 'transcript_001'),
(1, 'https://server2.com/avengers_endgame_4k.m3u8', '4K', 'transcript_002'),
(2, 'https://server1.com/spiderman_nwh_1080p.m3u8', '1080p', 'transcript_003'),
(2, 'https://server1.com/spiderman_nwh_720p.m3u8', '720p', 'transcript_003'),
(3, 'https://server1.com/batman_1080p.m3u8', '1080p', NULL);

-- ==================================================
-- BACKUP AND MAINTENANCE
-- ==================================================

-- Cleanup old performance logs (run periodically)
DELETE FROM link_performance_log WHERE checked_at < DATE_SUB(NOW(), INTERVAL 30 DAY);

-- Cleanup old cache invalidation logs
DELETE FROM cache_invalidation_log WHERE timestamp < DATE_SUB(NOW(), INTERVAL 7 DAY);

-- Update movie statistics (can be run as scheduled job)
-- This would typically be done in application code or stored procedure 