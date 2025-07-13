# ParseWebLink - Movie Database with URL Parsing

A Django REST API system for managing movie links with master playlists and transcript support, including URL parsing fallback functionality.

## Features

- **Movie Database Management**: Store and retrieve movies with TMDB/IMDB IDs
- **Master Playlist Support**: Each m3u8 URL contains all quality variants
- **Transcript System**: External API references for transcript data
- **URL Parsing Fallback**: Automatically parse vidsrc.me URLs when database has no data
- **Redis Caching**: Efficient caching for parsed URLs
- **RESTful API**: Clean API endpoints for all operations

## API Endpoints

### 1. Movie Links (Basic)
```
GET /api/movie-links/?tmdb_id=12345&imdb_id=tt1234567
```

### 2. Movie Links with Fallback (NEW)
```
POST /api/movie-links/with-fallback/
Content-Type: application/json

{
    "imdb_id": "tt1234567",
    "tmdb_id": "12345"
}
```

**How it works:**
1. **Database Check**: First checks if movie exists in database
2. **URL Construction**: If not found, constructs vidsrc URLs:
   - `https://vidsrc.net/embed/movie?tmdb=12345` (from tmdb_id)
   - `https://vidsrc.to/embed/movie/tt1234567` (from imdb_id)
3. **Parsing**: Attempts to parse each URL until successful
4. **Response**: Returns data with source indicator

**Response when data exists in database:**
```json
{
    "source": "database",
    "movie": {
        "id": 1,
        "tmdb_id": "12345",
        "imdb_id": "tt1234567",
        "title": "Movie Title",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    },
    "links": [
        {
            "id": 1,
            "m3u8_url": "https://example.com/master.m3u8",
            "is_active": true,
            "transcript_id": "transcript_123",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "transcript": {
                "id": "transcript_123",
                "note": "Use this ID to fetch transcript data from external API server"
            }
        }
    ]
}
```

**Response when parsing URL (fallback):**
```json
{
    "source": "parsed",
    "imdb_id": "tt1234567",
    "tmdb_id": "12345",
    "source_url": "https://vidsrc.net/embed/movie?tmdb=12345",
    "source_domain": "vidsrc.net",
    "m3u8_url": "https://parsed.example.com/master.m3u8",
    "transcript_id": "transcript_456",
    "note": "This is a master playlist containing all quality variants",
    "transcript_note": "Use this ID to fetch transcript data from external API server",
    "parsed_data": {
        "file_url": "https://parsed.example.com/master.m3u8",
        "id": "transcript_456",
        "source_domain": "vidsrc.net"
    }
}
```

**Error Response (when parsing fails):**
```json
{
    "error": "Failed to parse any of the constructed URLs",
    "attempted_urls": [
        "https://vidsrc.net/embed/movie?tmdb=12345",
        "https://vidsrc.to/embed/movie/tt1234567"
    ],
    "parse_results": [
        {
            "url": "https://vidsrc.net/embed/movie?tmdb=12345",
            "result": {"error": "No iframe found"}
        },
        {
            "url": "https://vidsrc.to/embed/movie/tt1234567",
            "result": {"error": "Parsing failed"}
        }
    ]
}
```

### 3. Movie Management
```
POST /api/movies/
Content-Type: application/json

{
    "tmdb_id": "12345",
    "imdb_id": "tt1234567",
    "title": "Movie Title",
    "links": [
        {
            "m3u8_url": "https://example.com/master.m3u8",
            "transcript_id": "transcript_123",
            "is_active": true
        }
    ],
    "transcripts": [
        {
            "id": "transcript_123"
        }
    ]
}
```

### 4. Other Endpoints
- `GET /api/movies/search/?q=title&page=1&limit=10` - Search movies
- `GET /api/movies/stats/` - Get statistics
- `POST /api/transcripts/` - Create transcript ID reference
- `GET /api/health/` - Health check

## URL Parsing Features

The system includes automatic URL parsing for multiple vidsrc domains:

1. **Multi-domain Support**: 
   - `vidsrc.me` - Original parsing logic
   - `vidsrc.net` - TMDB-based URLs
   - `vidsrc.to` - IMDB-based URLs

2. **URL Construction**:
   - `https://vidsrc.net/embed/movie?tmdb={tmdb_id}` for TMDB IDs
   - `https://vidsrc.to/embed/movie/tt{imdb_id}` for IMDB IDs

3. **Smart Parsing**:
   - Attempts multiple URLs until successful
   - Extracts m3u8 master playlist URLs
   - Identifies transcript IDs from various sources
   - Handles nested iframe structures

4. **Redis Caching**: Parsed results are cached for 2 days

5. **Error Handling**: Detailed error responses with attempt logs

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Setup Redis server (default: localhost:6380)
4. Run Django migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the server:
   ```bash
   python manage.py runserver
   ```

## Configuration

- **Redis**: Configure in `api/views.py` (REDIS_HOST, REDIS_PORT, REDIS_DB)
- **Cache Expiry**: Default 2 days (CACHE_EXPIRE)
- **URL Parsing**: Supports vidsrc.me, vidsrc.net, and vidsrc.to domains

## Notes

- All m3u8 URLs are master playlists containing multiple quality variants
- Transcript data is fetched from external API servers using stored IDs
- URL parsing provides fallback when database has no data
- System automatically constructs appropriate URLs based on available IDs
- Supports both TMDB and IMDB ID formats
- System is designed for microservices architecture
