import math

from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .login_throttle import get_client_ip, locked_seconds, record_failure, reset_failures
from .models import User


class UserForm(UserCreationForm):
    # 닉네임 형식·중복(대소문자 무시) 검사는 User 모델(validate_nickname, clean)이 맡는다
    class Meta:
        model = User
        fields = ("username", "nickname")
        labels = {"username": "사용자ID"}


class LoginThrottleMixin:
    """AuthenticationForm에 로그인 시도 제한을 더한다. 잠겨 있으면 비밀번호를 확인하지 않는다."""
    LOCKED_CODE = 'too_many_attempts'

    def _locked_error(self, seconds):
        self.locked_seconds = seconds
        return ValidationError(
            '로그인에 여러 번 실패해 잠시 막혔습니다. %(minutes)d분 후에 다시 시도하세요.',
            code=self.LOCKED_CODE, params={'minutes': math.ceil(seconds / 60)})

    def clean(self):
        username = self.cleaned_data.get('username')
        if username is None or not self.cleaned_data.get('password'):
            return super().clean()  # 빈 칸 오류는 시도로 세지 않는다
        ip = get_client_ip(self.request)
        if seconds := locked_seconds(username, ip):
            raise self._locked_error(seconds)
        try:
            cleaned_data = super().clean()
        except ValidationError as e:
            # user_cache가 있으면 비밀번호는 맞고 권한이 없는 경우(관리자 화면의 일반 회원)라 세지 않는다
            wrong_password = e.code == 'invalid_login' and self.user_cache is None
            if wrong_password and (seconds := record_failure(username, ip)):
                raise self._locked_error(seconds) from e  # 이번 실패로 잠겼으면 바로 알린다
            raise
        reset_failures(username, ip)
        return cleaned_data


class LoginForm(LoginThrottleMixin, AuthenticationForm):
    """API 로그인용"""


class AdminLoginForm(LoginThrottleMixin, AdminAuthenticationForm):
    """관리자 화면 로그인용 (admin.site.login_form)"""
