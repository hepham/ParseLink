# Generated by Django 5.2.4 on 2025-07-13 15:23

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MovieLinkView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('movie_id', models.BigIntegerField()),
                ('tmdb_id', models.CharField(max_length=20, null=True)),
                ('imdb_id', models.CharField(max_length=20, null=True)),
                ('title', models.CharField(max_length=500)),
                ('link_id', models.BigIntegerField()),
                ('m3u8_url', models.URLField(max_length=2000)),
                ('transcript_id', models.CharField(max_length=50, null=True)),
                ('created_at', models.DateTimeField()),
            ],
            options={
                'db_table': 'v_active_movie_links',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='CacheInvalidationLog',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('table_name', models.CharField(max_length=50)),
                ('record_id', models.BigIntegerField()),
                ('action', models.CharField(max_length=10)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'cache_invalidation_log',
                'indexes': [models.Index(fields=['timestamp'], name='idx_cache_log_timestamp'), models.Index(fields=['table_name'], name='idx_cache_log_table')],
            },
        ),
        migrations.CreateModel(
            name='Movie',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('tmdb_id', models.CharField(blank=True, db_index=True, max_length=20, null=True)),
                ('imdb_id', models.CharField(blank=True, db_index=True, max_length=20, null=True)),
                ('title', models.CharField(max_length=500)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('deleted', 'Deleted')], default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'movies',
                'indexes': [models.Index(fields=['tmdb_id', 'imdb_id'], name='idx_movies_tmdb_imdb'), models.Index(fields=['status'], name='idx_movies_status'), models.Index(fields=['created_at'], name='idx_movies_created_at')],
                'constraints': [models.CheckConstraint(condition=models.Q(('tmdb_id__isnull', False), ('imdb_id__isnull', False), _connector='OR'), name='chk_movie_ids'), models.UniqueConstraint(fields=('tmdb_id', 'imdb_id'), name='uk_movie_tmdb_imdb')],
            },
        ),
        migrations.CreateModel(
            name='Transcript',
            fields=[
                ('id', models.CharField(max_length=50, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'transcripts',
                'indexes': [models.Index(fields=['created_at'], name='idx_transcripts_created_at')],
            },
        ),
        migrations.CreateModel(
            name='MovieLink',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('m3u8_url', models.URLField(max_length=2000, validators=[django.core.validators.URLValidator()])),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_type', models.CharField(choices=[('imdb', 'IMDB'), ('tmdb', 'TMDB')], max_length=10, null=True, blank=True, db_index=True)),
                ('movie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movie_links', to='api.movie')),
                ('transcript', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='movie_links', to='api.transcript')),
            ],
            options={
                'db_table': 'movie_links',
            },
        ),
        migrations.CreateModel(
            name='LinkPerformanceLog',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('response_time', models.IntegerField(blank=True, null=True)),
                ('status_code', models.IntegerField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('checked_at', models.DateTimeField(auto_now_add=True)),
                ('link', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='performance_logs', to='api.movielink')),
            ],
            options={
                'db_table': 'link_performance_log',
                'indexes': [models.Index(fields=['link'], name='idx_link_perf_link_id'), models.Index(fields=['checked_at'], name='idx_link_perf_checked_at'), models.Index(fields=['status_code'], name='idx_link_perf_status_code')],
            },
        ),
        migrations.AddIndex(
            model_name='movielink',
            index=models.Index(fields=['movie', 'is_active'], name='idx_movie_links_movie_active'),
        ),
        migrations.AddIndex(
            model_name='movielink',
            index=models.Index(fields=['is_active'], name='idx_movie_links_active'),
        ),
        migrations.AddIndex(
            model_name='movielink',
            index=models.Index(fields=['transcript'], name='idx_movie_links_transcript_id'),
        ),
        migrations.AddIndex(
            model_name='movielink',
            index=models.Index(fields=['created_at'], name='idx_movie_links_created_at'),
        ),
        migrations.AddIndex(
            model_name='movielink',
            index=models.Index(fields=['is_active', 'created_at'], name='idx_movie_links_active_created'),
        ),
        migrations.AddConstraint(
            model_name='movielink',
            constraint=models.UniqueConstraint(fields=('movie', 'm3u8_url'), name='uk_movie_link_unique'),
        ),
    ]
