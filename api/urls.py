from django.urls import path
from . import views

urlpatterns = [
    # Movie links API - Main endpoint for getting movie links
    path('movie-links/', views.MovieLinksAPIView.as_view(), name='movie-links'),
    
    # Movie links with fallback API - Get movie links with URL parsing fallback
    path('movie-links/with-fallback/', views.MovieLinksWithFallbackAPIView.as_view(), name='movie-links-with-fallback'),
    
    # Movie management API - Create/update movies
    path('movies/', views.MovieManagementAPIView.as_view(), name='movie-management'),
    
    # Movie link management API - Add/update individual links
    path('movie-links/manage/', views.MovieLinkManagementAPIView.as_view(), name='movie-link-management'),
    
    # Movie search API - Search movies by title
    path('movies/search/', views.MovieSearchAPIView.as_view(), name='movie-search'),
    
    # Movie statistics API - Get overall statistics
    path('movies/stats/', views.MovieStatsAPIView.as_view(), name='movie-stats'),
    
    # Transcript management API - Create/update transcripts
    path('transcripts/', views.TranscriptManagementAPIView.as_view(), name='transcript-management'),
    
    # Transcript retrieval API - Get specific transcript
    path('transcripts/<str:transcript_id>/', views.TranscriptManagementAPIView.as_view(), name='transcript-detail'),
    
    # Health check endpoint
    path('health/', views.health_check, name='health-check'),
    
    # Encryption endpoints
    path('encryption/public-key/', views.get_public_key_endpoint, name='get-public-key'),
    path('encryption/test/', views.EncryptionTestAPIView.as_view(), name='encryption-test'),
    path('encrypted/movie-links/', views.EncryptedMovieLinksAPIView.as_view(), name='encrypted-movie-links'),
] 