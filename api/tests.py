from django.test import TestCase, Client
from django.urls import reverse
import json
from django.conf import settings
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

class APITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        key = getattr(settings, 'AES_FIXED_KEY', b'parseweblink_aes_demo_key_32byte')
        # Nếu là bytes, giữ nguyên; nếu là str, encode
        if isinstance(key, str):
            key = key.encode('utf-8')
        # Đảm bảo đúng 32 bytes
        assert len(key) == 32, f"AES key must be 32 bytes, got {len(key)}"
        self.aes_key = key
        self.test_imdb_id = 'tt0137523'
        # self.test_tmdb_id = '550'
        self.test_movie_title = 'Test Movie'
        self.test_transcript_id = 'testid'
        

    def aes_encrypt(self, plaintext: bytes, key: bytes) -> str:
        iv = get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        ct_bytes = cipher.encrypt(pad(plaintext, AES.block_size))
        return base64.b64encode(iv + ct_bytes).decode()

    def aes_decrypt(self, ciphertext_b64: str, key: bytes) -> bytes:
        raw = base64.b64decode(ciphertext_b64)
        iv = raw[:16]
        ct = raw[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt

    def check_movie_link_response(self, data, expected_id=None):
        self.assertIsInstance(data, list)
        # print("data:", str(data)+"\n")
        for item in data:
            self.assertIn('id', item)
            self.assertIn('m3u8', item)
            self.assertIn('transcriptid', item)
            if expected_id:
                self.assertEqual(item['id'], expected_id)
            self.assertIsInstance(item['m3u8'], str)

    def test_health_check(self):
        resp = self.client.get('/api/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('status', resp.json())

    def test_encryption_public_key(self):
        resp = self.client.get('/api/encryption/public-key/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('public_key', resp.json())

    def test_encryption_test(self):
        resp = self.client.post('/api/encryption/test/', json.dumps({'test': 'data'}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('encrypted_data', resp.json())

    def test_movie_links(self):
        resp = self.client.post('/api/movie-links/', json.dumps({'imdb_id': self.test_imdb_id}), content_type='application/json')
        self.assertIn(resp.status_code, [200, 404, 500, 405])
        if resp.status_code == 200:
            self.check_movie_link_response(resp.json(), expected_id=self.test_imdb_id)

    def test_movie_links_with_fallback(self):
        resp = self.client.post('/api/movie-links/with-fallback/', json.dumps({'imdb_id': self.test_imdb_id}), content_type='application/json')
        self.assertIn(resp.status_code, [200, 404, 500])
        if resp.status_code == 200:
            self.check_movie_link_response(resp.json(), expected_id=self.test_imdb_id)

    def test_movie_links_force_parse(self):
        resp = self.client.post('/api/movie-links/force-parse/', json.dumps({'imdb_id': self.test_imdb_id}), content_type='application/json')
        self.assertIn(resp.status_code, [200, 404, 500])
        if resp.status_code == 200:
            self.check_movie_link_response(resp.json(), expected_id=self.test_imdb_id)

    def test_aes_movie_links_with_fallback(self):
        data = {'imdb_id': self.test_imdb_id}
        plaintext = json.dumps(data).encode()
        encrypted_data = self.aes_encrypt(plaintext, self.aes_key)
        print("encrypted_data:", encrypted_data)
        resp = self.client.post('/api/encryped/movie-links/with-fallback/', json.dumps({'encrypted_data': encrypted_data}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        encrypted_result = resp.json().get('encrypted_data')
        if encrypted_result:
            # print("encrypted_result:", encrypted_result)
            # print("\n")
            result = json.loads(self.aes_decrypt(encrypted_result, self.aes_key).decode())
            
            self.check_movie_link_response(result, expected_id=self.test_imdb_id)

    def test_aes_movie_links_force_parse(self):
        data = {'imdb_id': self.test_imdb_id}
        plaintext = json.dumps(data).encode()
        encrypted_data = self.aes_encrypt(plaintext, self.aes_key)
        resp = self.client.post('/api/encryped/movie-links/force-parse/', json.dumps({'encrypted_data': encrypted_data}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        encrypted_result = resp.json().get('encrypted_data')
        if encrypted_result:
            result = json.loads(self.aes_decrypt(encrypted_result, self.aes_key).decode())
            self.check_movie_link_response(result, expected_id=self.test_imdb_id)

    def test_encrypted_movie_links(self):
        resp = self.client.post('/api/encrypted/movie-links/', json.dumps({'imdb_id': self.test_imdb_id}), content_type='application/json')
        self.assertIn(resp.status_code, [200, 400, 500])
        if resp.status_code == 200:
            self.check_movie_link_response(resp.json(), expected_id=self.test_imdb_id)

    def test_movies_management(self):
        resp = self.client.post('/api/movies/', json.dumps({'imdb_id': self.test_imdb_id, 'title': self.test_movie_title}), content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 400, 500])
        if resp.status_code in [200, 201]:
            data = resp.json()
            self.assertIn('movie_id', data)

    def test_movie_link_management(self):
        resp = self.client.post('/api/movie-links/manage/', json.dumps({'imdb_id': self.test_imdb_id, 'm3u8_url': 'http://test.m3u8'}), content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 400, 404, 500])
        if resp.status_code in [200, 201]:
            data = resp.json()
            self.assertIn('id', data)
            self.assertIn('m3u8_url', data)

    def test_movies_search(self):
        resp = self.client.get('/api/movies/search/?q=Test')
        self.assertIn(resp.status_code, [200, 400, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('movies', data)
            self.assertIsInstance(data['movies'], list)

    def test_movies_stats(self):
        resp = self.client.get('/api/movies/stats/')
        self.assertIn(resp.status_code, [200, 400, 404])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('total_movies', data)

    def test_transcripts_management(self):
        resp = self.client.post('/api/transcripts/', json.dumps({'movie_id': 1, 'content': 'Test transcript'}), content_type='application/json')
        self.assertIn(resp.status_code, [200, 201, 400, 500])
        if resp.status_code in [200, 201]:
            data = resp.json()
            self.assertIn('id', data)
            self.assertIn('content', data)

    def test_transcript_detail(self):
        resp = self.client.get(f'/api/transcripts/{self.test_transcript_id}/')
        self.assertIn(resp.status_code, [200, 404, 400])
        if resp.status_code == 200:
            data = resp.json()
            self.assertIn('id', data)
            self.assertIn('content', data)
