from django.db import models
from django.core.validators import URLValidator
from django.db.models import UniqueConstraint, CheckConstraint, Q


class Movie(models.Model):
    """
    Movie model storing basic movie information with tmdb_id and imdb_id
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deleted', 'Deleted'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    tmdb_id = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    imdb_id = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    title = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'movies'
        constraints = [
            # Ensure at least one of tmdb_id or imdb_id is provided
            CheckConstraint(
                condition=Q(tmdb_id__isnull=False) | Q(imdb_id__isnull=False),
                name='chk_movie_ids'
            ),
            # Unique constraint on tmdb_id and imdb_id combination
            UniqueConstraint(
                fields=['tmdb_id', 'imdb_id'],
                name='uk_movie_tmdb_imdb'
            ),
        ]
        indexes = [
            models.Index(fields=['tmdb_id', 'imdb_id'], name='idx_movies_tmdb_imdb'),
            models.Index(fields=['status'], name='idx_movies_status'),
            models.Index(fields=['created_at'], name='idx_movies_created_at'),
        ]
    
    def __str__(self):
        return f"{self.title}"
    
    @classmethod
    def find_by_external_id(cls, tmdb_id=None, imdb_id=None):
        """
        Find movie by tmdb_id or imdb_id
        """
        if not tmdb_id and not imdb_id:
            return None
            
        query = cls.objects.filter(status='active')
        
        if tmdb_id and imdb_id:
            return query.filter(Q(tmdb_id=tmdb_id) | Q(imdb_id=imdb_id)).first()
        elif tmdb_id:
            return query.filter(tmdb_id=tmdb_id).first()
        elif imdb_id:
            return query.filter(imdb_id=imdb_id).first()
    
    def get_active_links(self):
        """
        Get all active links for this movie
        """
        return self.movie_links.filter(is_active=True).order_by('-created_at')
    
    def get_links_with_transcripts(self):
        """
        Get all active links with their transcript information
        """
        return self.movie_links.select_related('transcript').filter(is_active=True).order_by('-created_at')


class Transcript(models.Model):
    """
    Transcript model storing only ID reference for external API calls
    Actual transcript data is retrieved from external API server using this ID
    """
    id = models.CharField(max_length=50, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'transcripts'
        indexes = [
            models.Index(fields=['created_at'], name='idx_transcripts_created_at'),
        ]
    
    def __str__(self):
        return f"Transcript ID: {self.id}"


class MovieLink(models.Model):
    """
    Movie link model storing m3u8 master playlist links for each movie with transcript support
    Each m3u8 is a master playlist containing multiple quality variants
    """
    
    id = models.BigAutoField(primary_key=True)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_links')
    m3u8_url = models.URLField(max_length=2000, validators=[URLValidator()])
    is_active = models.BooleanField(default=True)
    transcript = models.ForeignKey(Transcript, on_delete=models.SET_NULL, null=True, blank=True, related_name='movie_links')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'movie_links'
        constraints = [
            # Unique constraint to prevent duplicate links (removed quality)
            UniqueConstraint(
                fields=['movie', 'm3u8_url'],
                name='uk_movie_link_unique'
            ),
        ]
        indexes = [
            models.Index(fields=['movie', 'is_active'], name='idx_movie_links_movie_active'),
            models.Index(fields=['is_active'], name='idx_movie_links_active'),
            models.Index(fields=['transcript'], name='idx_movie_links_transcript_id'),
            models.Index(fields=['created_at'], name='idx_movie_links_created_at'),
            models.Index(fields=['is_active', 'created_at'], name='idx_movie_links_active_created'),
        ]
    
    def __str__(self):
        return f"{self.movie.title} - Master Playlist ({self.m3u8_url[:50]}...)"
    

    
    @property
    def transcript_id(self):
        """
        Return transcript ID for backward compatibility
        """
        return self.transcript.id if self.transcript else None
    
    @classmethod
    def get_links_by_movie_ids(cls, tmdb_id=None, imdb_id=None):
        """
        Get movie links filtered by movie IDs
        Each link is a master playlist containing multiple quality variants
        """
        # First find the movie
        movie = Movie.find_by_external_id(tmdb_id=tmdb_id, imdb_id=imdb_id)
        if not movie:
            return cls.objects.none()
        
        # Filter links
        queryset = cls.objects.select_related('movie', 'transcript').filter(movie=movie, is_active=True)
        
        return queryset.order_by('-created_at')


class LinkPerformanceLog(models.Model):
    """
    Track performance and availability of movie links
    """
    id = models.BigAutoField(primary_key=True)
    link = models.ForeignKey(MovieLink, on_delete=models.CASCADE, related_name='performance_logs')
    response_time = models.IntegerField(null=True, blank=True)  # in milliseconds
    status_code = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'link_performance_log'
        indexes = [
            models.Index(fields=['link'], name='idx_link_perf_link_id'),
            models.Index(fields=['checked_at'], name='idx_link_perf_checked_at'),
            models.Index(fields=['status_code'], name='idx_link_perf_status_code'),
        ]
    
    def __str__(self):
        return f"{self.link} - {self.status_code} ({self.checked_at})"


class CacheInvalidationLog(models.Model):
    """
    Track cache invalidation events
    """
    id = models.BigAutoField(primary_key=True)
    table_name = models.CharField(max_length=50)
    record_id = models.BigIntegerField()
    action = models.CharField(max_length=10)  # INSERT, UPDATE, DELETE
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cache_invalidation_log'
        indexes = [
            models.Index(fields=['timestamp'], name='idx_cache_log_timestamp'),
            models.Index(fields=['table_name'], name='idx_cache_log_table'),
        ]
    
    def __str__(self):
        return f"{self.table_name} - {self.action} - {self.record_id}"


# Custom manager for MovieLink with transcript support
class MovieLinkManager(models.Manager):
    def with_transcripts(self):
        """
        Get all movie links with their transcript information
        """
        return self.select_related('movie', 'transcript').filter(is_active=True)
    

    
    def for_movie(self, movie_id):
        """
        Get all active links for a specific movie
        """
        return self.filter(movie_id=movie_id, is_active=True).order_by('-created_at')

# Add the custom manager to MovieLink
MovieLink.add_to_class('objects', MovieLinkManager())

# Create a view model for easy querying
class MovieLinkView(models.Model):
    """
    Model representing the v_active_movie_links view
    """
    movie_id = models.BigIntegerField()
    tmdb_id = models.CharField(max_length=20, null=True)
    imdb_id = models.CharField(max_length=20, null=True)
    title = models.CharField(max_length=500)
    link_id = models.BigIntegerField()
    m3u8_url = models.URLField(max_length=2000)
    transcript_id = models.CharField(max_length=50, null=True)
    created_at = models.DateTimeField()
    
    class Meta:
        managed = False  # This is a database view, not a table
        db_table = 'v_active_movie_links'
