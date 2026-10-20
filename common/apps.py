from django.apps import AppConfig


class CommonConfig(AppConfig):
    # User는 기존 auth_user(id: integer)를 이어받으므로 PK 타입을 바꾸지 않는다
    default_auto_field = 'django.db.models.AutoField'
    name = 'common'
