import sqlite3
from pathlib import Path

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone


class Command(BaseCommand):
    help = ('기본 auth.User를 쓰던 DB를 common.User로 넘긴다(1회, 서버를 멈춘 뒤 실행). '
            'auth_user 테이블은 그대로 두고 마이그레이션·콘텐츠 타입 기록만 고친다. 실행 후 migrate 한다.')
    requires_system_checks = []

    def handle(self, *args, **options):
        if 'auth_user' not in connection.introspection.table_names():
            self.stdout.write('auth_user 테이블이 없는 새 DB입니다. migrate만 실행하면 됩니다.')
            return
        recorder = MigrationRecorder(connection)
        # 0002까지 적용됐다면 마이그레이션 기록은 이미 새 구조다 (재실행해도 되돌리지 않는다)
        fix_records = ('common', '0002_user_nickname') not in recorder.applied_migrations()
        fix_content_types = ContentType.objects.filter(app_label='auth', model='user').exists()
        if not fix_content_types:  # auth.user 콘텐츠 타입이 없으면 전환을 마친 DB다
            self.stdout.write('이미 전환된 DB입니다. migrate만 실행하면 됩니다.')
            return

        self.stdout.write(f"common_profile 테이블: {'있음' if 'common_profile' in connection.introspection.table_names() else '없음'}")
        self._backup_sqlite()
        with transaction.atomic():
            if fix_records:
                # 예전 common 마이그레이션(Profile)을 지우고, auth_user를 이어받는 0001을 적용된 것으로 기록한다
                recorder.migration_qs.filter(app='common').delete()
                recorder.migration_qs.create(app='common', name='0001_initial', applied=timezone.now())
            # 회원 권한·관리자 기록이 가리키는 콘텐츠 타입을 auth.user → common.user로 옮긴다.
            # 새 코드로 migrate가 먼저 돌아 빈 common.user가 생겼다면 그것을 지우고 옮긴다.
            ContentType.objects.filter(app_label='common', model__in=['user', 'profile']).delete()
            ContentType.objects.filter(app_label='auth', model='user').update(app_label='common')
        self.stdout.write(self.style.SUCCESS('전환 기록을 마쳤습니다. 이제 migrate를 실행하세요.'))

    def _backup_sqlite(self):
        if connection.vendor != 'sqlite':
            self.stdout.write(self.style.WARNING('SQLite가 아니므로 자동 백업을 건너뜁니다. 미리 백업해 두세요.'))
            return
        db_path = Path(connection.settings_dict['NAME'])
        backup = db_path.with_name(f'{db_path.name}.bak-{timezone.localtime():%Y%m%d%H%M%S}')
        connection.ensure_connection()
        with sqlite3.connect(backup) as target:  # 열린 DB도 일관되게 복사하는 SQLite 백업 API
            connection.connection.backup(target)
        target.close()
        self.stdout.write(f'DB 백업: {backup}')
