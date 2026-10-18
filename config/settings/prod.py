from .base import *

DEBUG = False

ALLOWED_HOSTS = ['54.116.234.200','seo-loft.cc']

# collectstatic이 관리자 화면 CSS·JS를 모으는 곳. nginx가 직접 내보낸다
# (/home/ubuntu는 www-data가 들어갈 수 없어 /var/www에 둔다)
STATIC_ROOT = '/var/www/mysite-backend/static'