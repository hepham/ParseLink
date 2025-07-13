from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging
# Thêm imports cho URL parsing logic
import requests
from bs4 import BeautifulSoup
import redis
import hashlib
import re
from urllib.parse import urlparse, urljoin

from .models import Movie, MovieLink, Transcript, LinkPerformanceLog

logger = logging.getLogger(__name__)

# Redis config for URL parsing cache
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
CACHE_EXPIRE = 2 * 24 * 60 * 60  # 2 days

try:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
except Exception as e:
    logger.warning(f"Redis connection failed: {e}")
    r = None

def get_cache_key(url):
    """Generate cache key for URL"""
    return 'parsed_url:' + hashlib.sha256(url.encode()).hexdigest()

def get_url_cache_result(url):
    """Get parse result from Redis cache for a specific URL"""
    if not r:
        return None
    
    try:
        cache_key = get_cache_key(url)
        cached_data = r.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"Redis cache get failed for URL {url}: {e}")
    return None

def save_url_cache_result(url, parse_result):
    """Save parse result to Redis cache for a specific URL"""
    if not r or not parse_result:
        return
    
    try:
        cache_key = get_cache_key(url)
        r.setex(cache_key, CACHE_EXPIRE, json.dumps(parse_result))
        logger.info(f"Saved URL parse result to Redis cache: {cache_key}")
    except Exception as e:
        logger.warning(f"Redis cache save failed for URL {url}: {e}")

def get_cached_results_for_urls(urls):
    """Get cached results for multiple URLs, return dict of url -> result"""
    cached_results = {}
    for url in urls:
        result = get_url_cache_result(url)
        if result:
            cached_results[url] = result
    return cached_results

def save_to_database(imdb_id=None, tmdb_id=None, parse_results=None):
    """Save parsed results to database"""
    if not parse_results:
        return
    
    try:
        # Find or create movie
        movie = Movie.find_by_external_id(tmdb_id=tmdb_id, imdb_id=imdb_id)
        if not movie:
            # Create new movie with a default title
            title = f"Movie {imdb_id or tmdb_id}"
            movie = Movie.objects.create(
                tmdb_id=tmdb_id,
                imdb_id=imdb_id,
                title=title
            )
            logger.info(f"Created new movie: {movie.id}")
        
        # Save each successful parse result
        for result in parse_results:
            file_url = result.get('file_url')
            transcript_id = result.get('id')
            
            if file_url:
                # Create or get transcript if transcript_id exists
                transcript = None
                if transcript_id:
                    transcript, created = Transcript.objects.get_or_create(
                        id=transcript_id,
                        defaults={'id': transcript_id}
                    )
                
                # Create movie link
                movie_link, created = MovieLink.objects.get_or_create(
                    movie=movie,
                    m3u8_url=file_url,
                    defaults={
                        'transcript': transcript,
                        'is_active': True
                    }
                )
                
                if created:
                    logger.info(f"Created new movie link: {movie_link.id}")
                else:
                    logger.info(f"Movie link already exists: {movie_link.id}")
                    
    except Exception as e:
        logger.error(f"Failed to save to database: {e}")
        # Don't raise exception, just log error

def parse_vidsrc_url(url):
    """
    Parse vidsrc URLs to extract m3u8 file URL and transcript ID
    Supports both vidsrc.me, vidsrc.net, and vidsrc.to domains
    """
    try:
        # Check cache first
        cache_key = get_cache_key(url)
        if r:
            cached = r.get(cache_key)
            # if cached:
            #     return json.loads(cached)
        
        # Make initial request
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

        # Parse vidsrc.me embed URLs (original logic)
        if 'vidsrc.net/embed/movie' in url or "vidsrc.xyz/embed/movie" in url:

            body = soup.find('body')
            data_i = body.get('data-i') if body else None

        # Get iframe src
            iframe = soup.find('iframe')
            iframe_src = iframe['src'] if iframe and iframe.has_attr('src') else ''
            
            if not iframe_src:
                return {'error': 'No iframe found in the page'}
            
            # Ensure proper URL format
            if iframe_src.startswith('//'):
                iframe_url = 'https:' + iframe_src
            elif iframe_src.startswith('http'): 
                iframe_url = iframe_src
            else:
                iframe_url = iframe_src
            
            # Get iframe content
            iframe_resp = requests.get(iframe_url, timeout=10)
            iframe_resp.raise_for_status()
            iframe_content = iframe_resp.text
            
            # Parse for player iframe source
            player_iframe_src = None
            full_player_iframe_url = None
        
            match = re.search(r"loadIframe\s*\([^)]*\)\s*{[^}]*src:\s*['\"]([^'\"]+)['\"]", iframe_content, re.DOTALL)
            if match:
                player_iframe_src = match.group(1)
            
                # Build full URL
                parsed = urlparse(iframe_url)
                domain = f"{parsed.scheme}://{parsed.netloc}"
        
                if player_iframe_src and not player_iframe_src.startswith('http'):
                    if not player_iframe_src.startswith('/'):
                        player_iframe_src = '/' + player_iframe_src
                    full_player_iframe_url = domain + player_iframe_src
                else:
                    full_player_iframe_url = player_iframe_src
            
            # Get final m3u8 URL
                file_url = None
                if full_player_iframe_url:
                    try:
                        resp2 = requests.get(full_player_iframe_url, timeout=10)
                        resp2.raise_for_status()
                        content2 = resp2.text
                    
                    # Extract file URL
                        match2 = re.search(r"file:\s*['\"]([^'\"]+)['\"]", content2)
                        file_url = match2.group(1) if match2 else None
                    except Exception as e:
                        logger.warning(f"Failed to get file URL: {e}")
            
            result = {
                'file_url': file_url,
                'id': data_i,
                'player_iframe_src': player_iframe_src,
                'full_player_iframe_url': full_player_iframe_url,
                'source_domain': 'vidsrc.me'
            }

  
       
        else:
            # For other URLs, return basic info
                title = soup.title.string if soup.title else ''
                first_p = soup.find('p').get_text(strip=True) if soup.find('p') else ''
                result = {
                    'url': url,
                    'title': title,
                'first_paragraph': first_p,
                'source_domain': 'unknown'
                }
        
        # Cache the result
        if r:
            r.setex(cache_key, CACHE_EXPIRE, json.dumps(result))
        
        return result
        
    except Exception as e:
        logger.error(f"Error parsing URL {url}: {e}")
        return {'error': str(e)}

def construct_vidsrc_urls(tmdb_id=None, imdb_id=None):
    """
    Construct vidsrc URLs from tmdb_id or imdb_id
    """
    urls = []
    
    if tmdb_id:
        urls.append(f"https://vidsrc.net/embed/movie?tmdb={tmdb_id}")
    
    if imdb_id:
     
        urls.append(f"https://vidsrc.xyz/embed/movie/{imdb_id}")
    return urls


class MovieLinksAPIView(View):
    """
    API View to handle movie link requests with transcript support
    Returns master m3u8 playlists containing all quality variants
    """
    
    def get(self, request):
        """
        GET /api/movie-links/?tmdb_id=12345&imdb_id=tt1234567
        """
        try:
            # Get parameters from request
            tmdb_id = request.GET.get('tmdb_id')
            imdb_id = request.GET.get('imdb_id')
            
            # Validate parameters
            if not tmdb_id and not imdb_id:
                return JsonResponse({
                    'error': 'At least one of tmdb_id or imdb_id is required'
                }, status=400)
            
            # Find movie links (each m3u8 is a master playlist with multiple quality variants)
            links = MovieLink.get_links_by_movie_ids(
                tmdb_id=tmdb_id,
                imdb_id=imdb_id
            )
            
            if not links.exists():
                return JsonResponse({
                    'error': 'No movie found with the provided IDs'
                }, status=404)
            
            # Get movie info
            movie = links.first().movie
            
            # Prepare response data
            response_data = {
                'movie': {
                    'id': movie.id,
                    'tmdb_id': movie.tmdb_id,
                    'imdb_id': movie.imdb_id,
                    'title': movie.title,
                    'created_at': movie.created_at.isoformat(),
                    'updated_at': movie.updated_at.isoformat(),
                },
                'links': []
            }
            
            # Add links data (each m3u8_url is a master playlist with all quality variants)
            for link in links:
                link_data = {
                    'id': link.id,
                    'm3u8_url': link.m3u8_url,  # Master playlist containing all quality variants
                    'is_active': link.is_active,
                    'transcript_id': link.transcript_id,
                    'created_at': link.created_at.isoformat(),
                    'updated_at': link.updated_at.isoformat(),
                }
                
                # Add transcript ID if available (for external API call)
                if link.transcript:
                    link_data['transcript'] = {
                        'id': link.transcript.id,
                        'note': 'Use this ID to fetch transcript data from external API server'
                    }
                
                response_data['links'].append(link_data)
            
            return JsonResponse(response_data, safe=False)
            
        except Exception as e:
            logger.error(f"Error in movie links API: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class MovieManagementAPIView(View):
    """
    API View for managing movies and their master playlist links with transcript support
    Each m3u8 link is a master playlist containing multiple quality variants
    """
    
    def post(self, request):
        """
        POST /api/movies/
        Create or update a movie with links and transcripts
        """
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['title']
            if not all(field in data for field in required_fields):
                return JsonResponse({
                    'error': f'Missing required fields: {required_fields}'
                }, status=400)
            
            # Check if tmdb_id or imdb_id is provided
            if not data.get('tmdb_id') and not data.get('imdb_id'):
                return JsonResponse({
                    'error': 'At least one of tmdb_id or imdb_id is required'
                }, status=400)
            
            with transaction.atomic():
                # Try to find existing movie
                movie = Movie.find_by_external_id(
                    tmdb_id=data.get('tmdb_id'),
                    imdb_id=data.get('imdb_id')
                )
                
                if movie:
                    # Update existing movie
                    movie.title = data.get('title', movie.title)
                    movie.save()
                else:
                    # Create new movie
                    movie = Movie.objects.create(
                        tmdb_id=data.get('tmdb_id'),
                        imdb_id=data.get('imdb_id'),
                        title=data['title'],
                    )
                
                # Process transcripts first if provided (only ID reference)
                if 'transcripts' in data:
                    for transcript_data in data['transcripts']:
                        Transcript.objects.get_or_create(
                            id=transcript_data['id']
                        )
                
                # Add links if provided (each m3u8_url is a master playlist)
                if 'links' in data:
                    for link_data in data['links']:
                        transcript = None
                        if link_data.get('transcript_id'):
                            try:
                                transcript = Transcript.objects.get(id=link_data['transcript_id'])
                            except Transcript.DoesNotExist:
                                pass
                        
                        MovieLink.objects.update_or_create(
                            movie=movie,
                            m3u8_url=link_data['m3u8_url'],
                            defaults={
                                'is_active': link_data.get('is_active', True),
                                'transcript': transcript,
                            }
                        )
                
                return JsonResponse({
                    'message': 'Movie created/updated successfully',
                    'movie_id': movie.id,
                    'tmdb_id': movie.tmdb_id,
                    'imdb_id': movie.imdb_id,
                }, status=201)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON format'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in movie management API: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class MovieLinkManagementAPIView(View):
    """
    API View for managing individual master playlist links with transcript support
    Each m3u8_url represents a master playlist containing all quality variants
    """
    
    def post(self, request):
        """
        POST /api/movie-links/manage/
        Add a new master playlist link to a movie with optional transcript
        The m3u8_url should be a master playlist containing all quality variants
        """
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['m3u8_url']
            if not all(field in data for field in required_fields):
                return JsonResponse({
                    'error': f'Missing required fields: {required_fields}'
                }, status=400)
            
            # Check if tmdb_id or imdb_id is provided
            if not data.get('tmdb_id') and not data.get('imdb_id'):
                return JsonResponse({
                    'error': 'At least one of tmdb_id or imdb_id is required to identify the movie'
                }, status=400)
            
            # Find the movie
            movie = Movie.find_by_external_id(
                tmdb_id=data.get('tmdb_id'),
                imdb_id=data.get('imdb_id')
            )
            
            if not movie:
                return JsonResponse({
                    'error': 'Movie not found with the provided IDs'
                }, status=404)
            
            # Handle transcript if provided
            transcript = None
            if data.get('transcript_id'):
                try:
                    transcript = Transcript.objects.get(id=data['transcript_id'])
                except Transcript.DoesNotExist:
                    return JsonResponse({
                        'error': f'Transcript with ID {data["transcript_id"]} not found'
                    }, status=404)
            
            # Create or update the link
            link, created = MovieLink.objects.update_or_create(
                movie=movie,
                m3u8_url=data['m3u8_url'],
                defaults={
                    'is_active': data.get('is_active', True),
                    'transcript': transcript,
                }
            )
            
            action = 'created' if created else 'updated'
            
            return JsonResponse({
                'message': f'Master playlist link {action} successfully',
                'link_id': link.id,
                'movie_id': movie.id,
                'transcript_id': link.transcript_id,
                'note': 'M3U8 URL represents a master playlist containing all quality variants'
            }, status=201 if created else 200)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON format'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in movie link management API: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TranscriptManagementAPIView(View):
    """
    API View for managing transcript ID references
    Only creates transcript records with ID for external API calls
    """
    
    def post(self, request):
        """
        POST /api/transcripts/
        Create a transcript ID reference
        """
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['id']
            if not all(field in data for field in required_fields):
                return JsonResponse({
                    'error': f'Missing required fields: {required_fields}'
                }, status=400)
            
            # Create transcript ID reference
            transcript, created = Transcript.objects.get_or_create(
                id=data['id']
            )
            
            action = 'created' if created else 'already exists'
            
            return JsonResponse({
                'message': f'Transcript ID reference {action}',
                'transcript_id': transcript.id,
                'note': 'Use this ID to fetch transcript data from external API server',
            }, status=201 if created else 200)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON format'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in transcript management API: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)
    
    def get(self, request, transcript_id=None):
        """
        GET /api/transcripts/{transcript_id}/
        Check if transcript ID exists in the system
        """
        try:
            if not transcript_id:
                return JsonResponse({
                    'error': 'Transcript ID is required'
                }, status=400)
            
            try:
                transcript = Transcript.objects.get(id=transcript_id)
            except Transcript.DoesNotExist:
                return JsonResponse({
                    'error': 'Transcript ID not found'
                }, status=404)
            
            return JsonResponse({
                'id': transcript.id,
                'created_at': transcript.created_at.isoformat(),
                'updated_at': transcript.updated_at.isoformat(),
                'note': 'Use this ID to fetch transcript data from external API server'
            })
            
        except Exception as e:
            logger.error(f"Error in transcript retrieval API: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


class MovieSearchAPIView(View):
    """
    API View for searching movies
    """
    
    def get(self, request):
        """
        GET /api/movies/search/?q=title&page=1&limit=10
        """
        try:
            query = request.GET.get('q', '').strip()
            page = int(request.GET.get('page', 1))
            limit = min(int(request.GET.get('limit', 10)), 100)  # Max 100 per page
            
            if not query:
                return JsonResponse({
                    'error': 'Search query is required'
                }, status=400)
            
            # Search movies by title
            movies = Movie.objects.filter(
                title__icontains=query,
                status='active'
            ).order_by('-created_at')
            
            # Paginate results
            paginator = Paginator(movies, limit)
            page_obj = paginator.get_page(page)
            
            # Prepare response
            response_data = {
                'movies': [],
                'pagination': {
                    'current_page': page_obj.number,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            }
            
            # Add movie data
            for movie in page_obj:
                link_count = movie.movie_links.filter(is_active=True).count()
                transcript_count = movie.movie_links.filter(
                    is_active=True,
                    transcript__isnull=False
                ).count()
                
                response_data['movies'].append({
                    'id': movie.id,
                    'tmdb_id': movie.tmdb_id,
                    'imdb_id': movie.imdb_id,
                    'title': movie.title,
                    'link_count': link_count,
                    'transcript_count': transcript_count,
                    'created_at': movie.created_at.isoformat(),
                })
            
            return JsonResponse(response_data, safe=False)
            
        except ValueError:
            return JsonResponse({
                'error': 'Invalid page or limit parameter'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in movie search API: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


class MovieStatsAPIView(View):
    """
    API View for getting movie statistics
    """
    
    def get(self, request):
        """
        GET /api/movies/stats/
        Get overall movie statistics
        """
        try:
            # Get basic statistics
            stats = {
                'total_movies': Movie.objects.filter(status='active').count(),
                'total_links': MovieLink.objects.filter(is_active=True).count(),
                'total_transcripts': Transcript.objects.count(),
                'movies_with_links': Movie.objects.filter(
                    status='active',
                    movie_links__is_active=True
                ).distinct().count(),
                'links_with_transcripts': MovieLink.objects.filter(
                    is_active=True,
                    transcript__isnull=False
                ).count(),
            }
            
            # Each link is now a master playlist containing multiple quality variants
            # No need for quality distribution statistics
            
            # Transcript statistics (only ID count available)
            stats['transcript_ids_count'] = Transcript.objects.count()
            
            return JsonResponse(stats)
            
        except Exception as e:
            logger.error(f"Error in movie stats API: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class MovieLinksWithFallbackAPIView(View):
    """
    API View to handle movie link requests with fallback to URL parsing
    If database doesn't have data, it will construct and parse vidsrc URLs
    """
    
    def post(self, request):
        """
        POST /api/movie-links/with-fallback/
        Get movie links with fallback to URL parsing
        Body: {
            "imdb_id": "tt1234567",
            "tmdb": "12345" (can use either tmdb or tmdb_id)
        }
        Response: [{
            "id": "imdb_id or tmdb_id",
            "m3u8": "m3u8_url",
            "transcriptid": "transcript_id"
        }]
        """
        try:
            data = json.loads(request.body)
            
            # Get parameters from request body - support both tmdb and tmdb_id
            imdb_id = data.get('imdb_id')
            tmdb_id = data.get('tmdb_id') or data.get('tmdb')

            # Validate parameters
            if not imdb_id and not tmdb_id:
                return JsonResponse({
                    'error': 'At least one of imdb_id or tmdb is required'
                }, status=400)
            
            # Step 1: Try to find existing movie links in database

            links = MovieLink.get_links_by_movie_ids(
                tmdb_id=tmdb_id,
                imdb_id=imdb_id
            )

            if links.exists():
                # Database has data, return existing links in new format

                result_array = []
                
                for link in links:
                    movie = link.movie
                    # Use IMDB ID if available, otherwise TMDB ID
                    movie_id = movie.imdb_id if movie.imdb_id else movie.tmdb_id
                    
                    link_item = {
                        "id": movie_id,
                        "m3u8": link.m3u8_url,
                        "transcriptid": link.transcript_id if link.transcript_id else ""
                    }
                    result_array.append(link_item)
                
                return JsonResponse(result_array, safe=False)
            
            else:
                # Database doesn't have data, fallback to URL parsing
                logger.info(f"No database data found for imdb_id: {imdb_id}, tmdb_id: {tmdb_id}, constructing vidsrc URLs")
                
                # Construct vidsrc URLs from IDs
                urls_to_parse = construct_vidsrc_urls(tmdb_id=tmdb_id, imdb_id=imdb_id)
                
                if not urls_to_parse:
                    return JsonResponse({
                        'error': 'No valid URLs could be constructed from provided IDs'
                    }, status=400)
                

                
                # Step 2: Check cache for each URL first
                cached_results = {}
                urls_to_actually_parse = []
                
                for url in urls_to_parse:
                    cached_result = get_url_cache_result(url)
                    if cached_result:
                        cached_results[url] = cached_result
                    else:
                        urls_to_actually_parse.append(url)
                
                # Step 3: Parse URLs that don't have cache
                successful_results = []
                
                # Add cached results to successful results
                for url, cached_result in cached_results.items():
                    if cached_result.get('file_url') and 'error' not in cached_result:
                        cached_result['source_url'] = url
                        successful_results.append(cached_result)
                
                # Parse remaining URLs
                for i, url in enumerate(urls_to_actually_parse, 1):
                    logger.info(f"Attempting to parse URL: {url}")
                    
                    parse_result = parse_vidsrc_url(url)
                    
                    # If we got a file_url, consider this a good result
                    if parse_result.get('file_url') and 'error' not in parse_result:
                        parse_result['source_url'] = url
                        successful_results.append(parse_result)
                        
                        # Save to cache immediately
                        save_url_cache_result(url, parse_result)
                

                
                # If no successful result, return error
                if not successful_results:
                    return JsonResponse({
                        'error': 'Failed to parse any of the constructed URLs',
                        'attempted_urls': urls_to_parse
                    }, status=500)
                
                # Step 4: Save parsed results to database
                save_to_database(imdb_id=imdb_id, tmdb_id=tmdb_id, parse_results=successful_results)
                
                # Prepare response in new array format - one item per successful result
                result_array = []
                
                for result in successful_results:
                    # Use IMDB ID if available, otherwise TMDB ID  
                    movie_id = imdb_id if imdb_id else tmdb_id
                    
                    link_item = {
                        "id": movie_id,
                        "m3u8": result.get('file_url', ''),
                        "transcriptid": result.get('id', '')
                    }
                    result_array.append(link_item)
                
                return JsonResponse(result_array, safe=False)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON format'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in movie links with fallback API: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)


# Health check endpoint
def health_check(request):
    """
    Simple health check endpoint
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'movie-links-api',
        'version': 'v3',
        'features': {
            'transcripts': True,
            'master_playlists': True,
            'movie_search': True,
            'statistics': True
        },
        'note': 'All m3u8 URLs are master playlists containing multiple quality variants'
    })
