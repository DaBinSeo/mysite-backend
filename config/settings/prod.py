from .base import *

DEBUG = False

ALLOWED_HOSTS = ['54.116.234.200','seo-loft.cc']

# collectstatic이 관리자 화면 CSS·JS를 모으는 곳. nginx가 직접 내보낸다
# (/home/ubuntu는 www-data가 들어갈 수 없어 /var/www에 둔다)
STATIC_ROOT = '/var/www/mysite-backend/static'

# nginx가 HTTPS를 받아 X-Forwarded-Proto로 넘긴다(사이트맵 주소 등이 https로 만들어지도록)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
