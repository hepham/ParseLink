-- ==================================================
-- DATABASE DESIGN FOR MOVIE WEBSITE WITH M3U8 LINKS
-- ==================================================

-- 1. MOVIES TABLE
-- Stores basic movie information with tmdb_id and imdb_id
CREATE TABLE movies (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    tmdb_id VARCHAR(20) NULL,
    imdb_id VARCHAR(20) NULL,
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    release_year INT,
    poster_url VARCHAR(1000),
    overview TEXT,
    runtime INT,
    status ENUM('active', 'inactive', 'deleted') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_movie_ids CHECK (tmdb_id IS NOT NULL OR imdb_id IS NOT NULL),
    CONSTRAINT uk_movie_tmdb_imdb UNIQUE (tmdb_id, imdb_id)
);

-- 2. MOVIE_LINKS TABLE
-- Stores m3u8 links for each movie
CREATE TABLE movie_links (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    movie_id BIGINT NOT NULL,
    server_name VARCHAR(100) NOT NULL,
    m3u8_url VARCHAR(2000) NOT NULL,
    quality VARCHAR(20) NOT NULL, -- e.g., '720p', '1080p', '4K'
    language VARCHAR(10) NOT NULL, -- e.g., 'vi', 'en', 'ko'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign key
    CONSTRAINT fk_movie_links_movie_id FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
    
    -- Unique constraint to prevent duplicate links
    CONSTRAINT uk_movie_link_unique UNIQUE (movie_id, server_name, quality, language)
);

-- 3. INDEXES FOR PERFORMANCE
-- Primary search indexes
CREATE INDEX idx_movies_tmdb_id ON movies(tmdb_id);
CREATE INDEX idx_movies_imdb_id ON movies(imdb_id);
CREATE INDEX idx_movies_tmdb_imdb ON movies(tmdb_id, imdb_id);

-- Movie links indexes
CREATE INDEX idx_movie_links_movie_id ON movie_links(movie_id);
CREATE INDEX idx_movie_links_server_quality ON movie_links(server_name, quality);
CREATE INDEX idx_movie_links_active ON movie_links(is_active);
CREATE INDEX idx_movie_links_created_at ON movie_links(created_at);

-- Composite indexes for common queries
CREATE INDEX idx_movie_links_movie_active ON movie_links(movie_id, is_active);
CREATE INDEX idx_movie_links_quality_lang ON movie_links(quality, language);

-- ==================================================
-- SAMPLE QUERIES
-- ==================================================

-- 1. Query links by tmdb_id
SELECT 
    m.id as movie_id,
    m.title,
    m.tmdb_id,
    m.imdb_id,
    ml.server_name,
    ml.m3u8_url,
    ml.quality,
    ml.language,
    ml.is_active,
    ml.created_at
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
WHERE m.tmdb_id = '12345' 
  AND ml.is_active = TRUE
ORDER BY ml.quality DESC, ml.server_name;

-- 2. Query links by imdb_id
SELECT 
    m.id as movie_id,
    m.title,
    m.tmdb_id,
    m.imdb_id,
    ml.server_name,
    ml.m3u8_url,
    ml.quality,
    ml.language,
    ml.is_active,
    ml.created_at
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
WHERE m.imdb_id = 'tt1234567' 
  AND ml.is_active = TRUE
ORDER BY ml.quality DESC, ml.server_name;

-- 3. Query links by both tmdb_id and imdb_id (more precise)
SELECT 
    m.id as movie_id,
    m.title,
    m.tmdb_id,
    m.imdb_id,
    ml.server_name,
    ml.m3u8_url,
    ml.quality,
    ml.language,
    ml.is_active,
    ml.created_at
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
WHERE (m.tmdb_id = '12345' OR m.imdb_id = 'tt1234567')
  AND ml.is_active = TRUE
ORDER BY ml.quality DESC, ml.server_name;

-- 4. Query with specific quality and language filters
SELECT 
    m.title,
    ml.server_name,
    ml.m3u8_url,
    ml.quality,
    ml.language
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
WHERE m.tmdb_id = '12345' 
  AND ml.is_active = TRUE
  AND ml.quality IN ('1080p', '720p')
  AND ml.language = 'vi'
ORDER BY 
    CASE ml.quality 
        WHEN '1080p' THEN 1
        WHEN '720p' THEN 2
        ELSE 3
    END,
    ml.server_name;

-- 5. Insert or update movie (upsert pattern)
INSERT INTO movies (tmdb_id, imdb_id, title, original_title, release_year)
VALUES ('12345', 'tt1234567', 'Movie Title', 'Original Title', 2023)
ON DUPLICATE KEY UPDATE
    title = VALUES(title),
    original_title = VALUES(original_title),
    release_year = VALUES(release_year),
    updated_at = CURRENT_TIMESTAMP;

-- 6. Add new m3u8 link
INSERT INTO movie_links (movie_id, server_name, m3u8_url, quality, language)
SELECT 
    m.id,
    'Server1',
    'https://server1.com/movie.m3u8',
    '1080p',
    'vi'
FROM movies m
WHERE m.tmdb_id = '12345'
ON DUPLICATE KEY UPDATE
    m3u8_url = VALUES(m3u8_url),
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

-- Procedure to get all links for a movie
DELIMITER //
CREATE PROCEDURE get_movie_links(
    IN p_tmdb_id VARCHAR(20),
    IN p_imdb_id VARCHAR(20),
    IN p_quality VARCHAR(20),
    IN p_language VARCHAR(10)
)
BEGIN
    SELECT 
        m.id as movie_id,
        m.title,
        m.tmdb_id,
        m.imdb_id,
        ml.server_name,
        ml.m3u8_url,
        ml.quality,
        ml.language,
        ml.is_active,
        ml.created_at
    FROM movies m
    JOIN movie_links ml ON m.id = ml.movie_id
    WHERE (p_tmdb_id IS NULL OR m.tmdb_id = p_tmdb_id)
      AND (p_imdb_id IS NULL OR m.imdb_id = p_imdb_id)
      AND (p_quality IS NULL OR ml.quality = p_quality)
      AND (p_language IS NULL OR ml.language = p_language)
      AND ml.is_active = TRUE
    ORDER BY 
        CASE ml.quality 
            WHEN '4K' THEN 1
            WHEN '1080p' THEN 2
            WHEN '720p' THEN 3
            WHEN '480p' THEN 4
            ELSE 5
        END,
        ml.server_name;
END//
DELIMITER ;

-- ==================================================
-- PERFORMANCE OPTIMIZATIONS
-- ==================================================

-- 1. Create a materialized view for frequently accessed data
CREATE VIEW v_active_movie_links AS
SELECT 
    m.id as movie_id,
    m.tmdb_id,
    m.imdb_id,
    m.title,
    ml.id as link_id,
    ml.server_name,
    ml.m3u8_url,
    ml.quality,
    ml.language,
    ml.created_at
FROM movies m
JOIN movie_links ml ON m.id = ml.movie_id
WHERE ml.is_active = TRUE
  AND m.status = 'active';

-- 2. Create partitioned table for large datasets (optional)
-- If you expect millions of links, consider partitioning by created_at
-- ALTER TABLE movie_links PARTITION BY RANGE (YEAR(created_at)) (
--     PARTITION p2023 VALUES LESS THAN (2024),
--     PARTITION p2024 VALUES LESS THAN (2025),
--     PARTITION p_future VALUES LESS THAN MAXVALUE
-- );

-- ==================================================
-- ADDITIONAL TABLES FOR ADVANCED FEATURES
-- ==================================================

-- Table for tracking link health/availability
CREATE TABLE link_health (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    link_id BIGINT NOT NULL,
    status ENUM('active', 'inactive', 'error') DEFAULT 'active',
    response_time INT, -- in milliseconds
    error_message TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_link_health_link_id FOREIGN KEY (link_id) REFERENCES movie_links(id) ON DELETE CASCADE
);

-- Table for user preferences and ratings
CREATE TABLE user_link_preferences (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT, -- Reference to your user table
    link_id BIGINT NOT NULL,
    preference_score INT DEFAULT 0, -- User rating
    usage_count INT DEFAULT 0,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_user_pref_link_id FOREIGN KEY (link_id) REFERENCES movie_links(id) ON DELETE CASCADE,
    CONSTRAINT uk_user_link_pref UNIQUE (user_id, link_id)
);

-- Index for link health monitoring
CREATE INDEX idx_link_health_link_id ON link_health(link_id);
CREATE INDEX idx_link_health_status ON link_health(status);
CREATE INDEX idx_link_health_checked_at ON link_health(checked_at); 