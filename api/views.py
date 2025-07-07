from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from bs4 import BeautifulSoup
import redis
import hashlib
import json
from django.conf import settings
from datetime import timedelta
import re
from urllib.parse import urlparse, urljoin

# Redis config (có thể điều chỉnh theo settings thực tế)
REDIS_HOST = 'localhost'
REDIS_PORT = 6380
REDIS_DB = 0
CACHE_EXPIRE = 2 * 24 * 60 * 60  # 2 ngày (giây)

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

def get_cache_key(url):
    return 'parsed_url:' + hashlib.sha256(url.encode()).hexdigest()

class ParseUrlView(APIView):
    def post(self, request):
        url = request.data.get('url')
        if not url:
            return Response({'error': 'Missing URL'}, status=status.HTTP_400_BAD_REQUEST)
        cache_key = get_cache_key(url)
        cached = r.get(cache_key)
        print('DEBUG: cached =', cached)
        if cached:
            return Response(json.loads(cached), status=status.HTTP_200_OK)
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Nếu là vidsrc.me, lấy src của iframe đầu tiên
            if 'vidsrc.me/embed/movie' in url:
                # print(soup)
                body = soup.find('body')
                data_i = body.get('data-i') if body else None

                iframe = soup.find('iframe')
                # print(iframe)
                iframe_src = iframe['src'] if iframe and iframe.has_attr('src') else ''
                # print('DEBUG: iframe_src =', iframe_src)
                iframe_content = ''
                if iframe_src:
                    # Đảm bảo có http(s):
                    if iframe_src.startswith('//'):
                        iframe_url = 'https:' + iframe_src
                    elif iframe_src.startswith('http'): 
                        iframe_url = iframe_src
                    else:
                        iframe_url = iframe_src
                    # print('DEBUG: iframe_url =', iframe_url)
                    try:
                        iframe_resp = requests.get(iframe_url, timeout=10)
                        iframe_resp.raise_for_status()
                        iframe_content = iframe_resp.text
                        # print('DEBUG: iframe_content (first 500 chars) =', iframe_content[:500])
                    except Exception as e:
                        iframe_content = f'Error fetching iframe src: {str(e)}'
                        # print('DEBUG: iframe_content ERROR =', iframe_content)
                player_iframe_src = None
                full_player_iframe_url = None
                if iframe_content:
                    match = re.search(r"loadIframe\s*\([^)]*\)\s*{[^}]*src:\s*['\"]([^'\"]+)['\"]", iframe_content, re.DOTALL)
                    if match:
                        player_iframe_src = match.group(1)
                        # print('DEBUG: player_iframe_src =', player_iframe_src)
                        # Lấy domain từ iframe_url và ghép với player_iframe_src nếu player_iframe_src là path
                        parsed = urlparse(iframe_url)
                        domain = f"{parsed.scheme}://{parsed.netloc}"
                        if player_iframe_src and not player_iframe_src.startswith('http'):
                            if not player_iframe_src.startswith('/'):
                                player_iframe_src = '/' + player_iframe_src
                            full_player_iframe_url = domain + player_iframe_src
                        else:
                            full_player_iframe_url = player_iframe_src
                        # print('DEBUG: full_player_iframe_url =', full_player_iframe_url)
                result = {
                    # 'url': url,
                    # 'iframe_src': iframe_src,
                    # 'iframe_content': iframe_content,
                    'player_iframe_src': player_iframe_src,
                    'full_player_iframe_url': full_player_iframe_url
                }
                # Gọi full_player_iframe_url và parse lấy file_url nếu có
                file_url = None
                if full_player_iframe_url:
                    try:
                        resp2 = requests.get(full_player_iframe_url, timeout=10)
                        resp2.raise_for_status()
                        content2 = resp2.text
                        match2 = re.search(r"file:\s*['\"]([^'\"]+)['\"]", content2)
                        file_url = match2.group(1) if match2 else None
                        # print('DEBUG: file_url =', file_url)
                    except Exception as e:
                        # print('DEBUG: file_url ERROR =', str(e))
                        pass
                # Chỉ trả về link m3u8
                # if file_url and file_url.endswith('.m3u8'):
                #     try:
                #         m3u8_resp = requests.get(file_url, timeout=10)
                #         m3u8_resp.raise_for_status()
                #         m3u8_text = m3u8_resp.text
                #         # Parse m3u8 for resolutions and links
                #         result_list = []
                #         parsed_file_url = urlparse(file_url)
                #         domain = f"{parsed_file_url.scheme}://{parsed_file_url.netloc}"
                #         for i, line in enumerate(m3u8_text.splitlines()):
                #             if line.startswith('#EXT-X-STREAM-INF:'):
                #                 match = re.search(r'RESOLUTION=(\d+x\d+)', line)
                #                 if match and i + 1 < len(m3u8_text.splitlines()):
                #                     resolution = match.group(1).replace('x', '*')
                #                     m3u8_link = m3u8_text.splitlines()[i + 1].strip()
                #                     # Prepend domain if m3u8_link is relative
                #                     if not m3u8_link.startswith('http'):
                #                         if m3u8_link.startswith('/'):
                #                             m3u8_link = domain + m3u8_link
                #                         else:
                #                             # handle relative to file_url path
                #                             m3u8_link = urljoin(file_url, m3u8_link)
                #                     result_list.append({'resolutions': resolution, 'link': m3u8_link})
                #         result = {'result': result_list}
                #     except Exception as e:
                #         result = {'file_url': file_url, 'error': f'Failed to parse m3u8: {str(e)}'}
                # else:
                    result = {'file_url': file_url,
                              'id': data_i}
            else:
                # Lấy tiêu đề và đoạn đầu tiên làm ví dụ
                title = soup.title.string if soup.title else ''
                first_p = soup.find('p').get_text(strip=True) if soup.find('p') else ''
                result = {
                    'url': url,
                    'title': title,
                    'first_paragraph': first_p
                }
            r.setex(cache_key, CACHE_EXPIRE, json.dumps(result))
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
