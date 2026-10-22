"""
URL configuration for config project.

화면은 frontend(React)가 담당하고, 백엔드는 JSON API와 관리자 화면만 제공한다.
API는 버전별로 연결한다. 새 버전은 path('api/v2/', include('pybo.api.v2.urls'))처럼 추가한다.
/sitemap.xml은 검색엔진용 사이트맵이다(게이트웨이가 이 경로만 장고로 보낸다).
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include

from pybo.sitemaps import sitemaps

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('pybo.api.v1.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
]
