import re

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

NICKNAME_PATTERN = re.compile(r'[가-힣A-Za-z0-9]+')
HANGUL_PATTERN = re.compile(r'[가-힣]')


def validate_nickname(nickname):
    if not NICKNAME_PATTERN.fullmatch(nickname):
        raise ValidationError("닉네임에는 한글(완성형)·영문·숫자만 쓸 수 있습니다. 공백·특수문자는 안 됩니다.")
    min_length = 2 if HANGUL_PATTERN.search(nickname) else 3
    if len(nickname) < min_length:
        raise ValidationError("닉네임은 한글이 들어가면 2자, 영문·숫자만이면 3자 이상이어야 합니다.")


class User(AbstractUser):
    """이름·성 대신 닉네임을 쓰는 회원. 기본 User에서 이어받아 테이블은 auth_user 그대로 쓴다."""
    first_name = None
    last_name = None
    nickname = models.CharField(
        '닉네임', max_length=20, unique=True, validators=[validate_nickname],
        help_text="한글·영문·숫자만 쓸 수 있습니다. 한글이 들어가면 2자, 아니면 3자 이상입니다.")

    REQUIRED_FIELDS = ['email', 'nickname']

    class Meta(AbstractUser.Meta):
        db_table = 'auth_user'

    def clean(self):
        # 대소문자만 다른 닉네임도 중복으로 본다 (회원가입 폼과 관리자 화면 모두 거친다)
        super().clean()
        if self.nickname and User.objects.filter(nickname__iexact=self.nickname).exclude(pk=self.pk).exists():
            raise ValidationError({'nickname': "이미 사용 중인 닉네임입니다."})

    def __str__(self):
        return self.username


class RefreshToken(models.Model):
    """발급한 refresh 토큰(jti). 갱신하면 새 토큰으로 바꾸고, 쓴 토큰·로그아웃한 토큰은 revoked_at을 채운다."""
    jti = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refresh_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.user} ({self.jti[:8]})'


class LoginFailure(models.Model):
    """로그인 실패 횟수 (계정+IP 조합마다 한 줄). 로그인에 성공하거나 기간이 지나면 지운다."""
    username = models.CharField('사용자ID', max_length=150)
    ip = models.CharField('IP', max_length=45)
    failures = models.PositiveSmallIntegerField('실패 횟수', default=0)
    last_failed_at = models.DateTimeField('마지막 실패')
    locked_until = models.DateTimeField('잠금 해제', null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = '로그인 실패'
        constraints = [models.UniqueConstraint(fields=['username', 'ip'], name='unique_login_failure')]
        indexes = [models.Index(fields=['last_failed_at'])]

    def __str__(self):
        return f'{self.username} ({self.ip})'
