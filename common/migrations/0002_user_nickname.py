# 이름·성 컬럼을 없애고 닉네임을 User에 둔다.
# 예전 Profile 테이블(common_profile)이 남아 있으면 그 닉네임을 옮기고 테이블을 지운다.
# 닉네임이 없는 기존 회원에게는 '회원{id}'를 넣는다.

import common.models
from django.db import migrations, models

PROFILE_TABLE = 'common_profile'


def fill_nickname(apps, schema_editor):
    User = apps.get_model('common', 'User')
    connection = schema_editor.connection
    profile_nicknames = {}
    if PROFILE_TABLE in connection.introspection.table_names():
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT user_id, nickname FROM {PROFILE_TABLE}')
            profile_nicknames = dict(cursor.fetchall())
        schema_editor.execute(f'DROP TABLE {PROFILE_TABLE}')
    users = list(User.objects.filter(nickname__isnull=True).order_by('pk'))
    # Profile 닉네임을 먼저 채운 뒤, 나머지에 겹치지 않는 '회원{id}'를 붙인다
    used = {nickname.lower() for nickname in profile_nicknames.values()}
    for user in users:
        nickname = profile_nicknames.get(user.pk)
        if not nickname:
            nickname, n = f'회원{user.pk}', 1
            while nickname.lower() in used:
                nickname, n = f'회원{user.pk}x{n}', n + 1
            used.add(nickname.lower())
        user.nickname = nickname
        user.save(update_fields=['nickname'])


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='user',
            name='last_name',
        ),
        migrations.AddField(
            model_name='user',
            name='nickname',
            field=models.CharField(max_length=20, null=True, verbose_name='닉네임'),
        ),
        migrations.RunPython(fill_nickname, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='nickname',
            field=models.CharField(help_text='한글·영문·숫자만 쓸 수 있습니다. 한글이 들어가면 2자, 아니면 3자 이상입니다.', max_length=20, unique=True, validators=[common.models.validate_nickname], verbose_name='닉네임'),
        ),
    ]
