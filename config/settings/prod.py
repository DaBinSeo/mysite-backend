from .base import *

DEBUG = False

# IP(54.116.234.200)로 들어온 HTTPS는 nginx가 핸드셰이크를 거부하고, HTTP는 도메인으로 301 보낸다
ALLOWED_HOSTS = ['seo-loft.cc']

# collectstatic이 관리자 화면 CSS·JS를 모으는 곳. nginx가 직접 내보낸다
# (/home/ubuntu는 www-data가 들어갈 수 없어 /var/www에 둔다)
STATIC_ROOT = '/var/www/mysite-backend/static'

# nginx가 HTTPS를 받아 X-Forwarded-Proto로 넘긴다(사이트맵 주소 등이 https로 만들어지도록)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 관리자 화면의 세션·CSRF 쿠키를 HTTPS에서만 보낸다
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
