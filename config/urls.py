"""
URL configuration for config project.

화면은 frontend(React)가 담당하고, 백엔드는 JSON API와 관리자 화면만 제공한다.
API는 버전별로 연결한다. 새 버전은 path('api/v2/', include('pybo.api.v2.urls'))처럼 추가한다.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('pybo.api.v1.urls')),
]
