from django.urls import path, re_path

from . import answer_views, auth_views, question_views
from .utils import not_found

app_name = 'api_v1'

urlpatterns = [
    # question_views.py
    path('questions/', question_views.question_list_create, name='question_list'),
    path('questions/<int:question_id>/', question_views.question_detail, name='question_detail'),
    path('questions/<int:question_id>/vote/', question_views.question_vote, name='question_vote'),

    # answer_views.py
    path('questions/<int:question_id>/answers/', answer_views.answer_create, name='answer_create'),
    path('answers/<int:answer_id>/', answer_views.answer_detail, name='answer_detail'),
    path('answers/<int:answer_id>/vote/', answer_views.answer_vote, name='answer_vote'),

    # auth_views.py
    path('auth/signup/', auth_views.signup, name='signup'),
    path('auth/password-rules/', auth_views.password_rules, name='password_rules'),
    path('auth/login/', auth_views.login, name='login'),
    path('auth/refresh/', auth_views.refresh, name='refresh'),
    path('auth/me/', auth_views.me, name='me'),

    # 그 밖의 /api/v1/ 경로는 HTML이 아닌 JSON 404
    re_path(r'^.*$', not_found),
]
