import uuid
from datetime import timedelta
from functools import wraps

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from common.models import RefreshToken
from .utils import error_response

User = get_user_model()


class TokenError(Exception):
    pass


def _password_version(user):
    """비밀번호가 바뀌면 달라지는 값 (장고 세션이 쓰는 HMAC). 토큰에 넣어 두면 비밀번호 변경 시 기존 토큰이 모두 무효가 된다."""
    return user.get_session_auth_hash()[:16]


def _encode(user, token_type, lifetime, **claims):
    now = timezone.now()
    payload = {
        'sub': str(user.id),
        'type': token_type,
        'pwd': _password_version(user),
        'iat': now,
        'exp': now + lifetime,
        **claims,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user):
    return _encode(user, 'access', timedelta(minutes=settings.JWT_ACCESS_LIFETIME_MINUTES))


def create_refresh_token(user):
    """refresh 토큰은 jti를 DB에 남겨 한 번만 쓰고(회전), 로그아웃으로 폐기할 수 있게 한다."""
    lifetime = timedelta(days=settings.JWT_REFRESH_LIFETIME_DAYS)
    now = timezone.now()
    RefreshToken.objects.filter(expires_at__lt=now).delete()  # 만료된 기록 정리
    jti = uuid.uuid4().hex
    RefreshToken.objects.create(jti=jti, user=user, expires_at=now + lifetime)
    return _encode(user, 'refresh', lifetime, jti=jti)


def issue_tokens(user):
    return {'access': create_access_token(user), 'refresh': create_refresh_token(user)}


def _decode(token, token_type):
    """서명·만료·종류·비밀번호 버전을 검증하고 (사용자, payload)를 돌려준다. 실패하면 TokenError."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={'require': ['exp', 'sub', 'type']},
        )
    except jwt.ExpiredSignatureError:
        raise TokenError('토큰이 만료되었습니다.')
    except jwt.InvalidTokenError:
        raise TokenError('유효하지 않은 토큰입니다.')
    if payload['type'] != token_type:
        raise TokenError('유효하지 않은 토큰입니다.')
    try:
        user = User.objects.get(pk=int(payload['sub']), is_active=True)
    except (User.DoesNotExist, ValueError):
        raise TokenError('사용자를 찾을 수 없습니다.')
    if not constant_time_compare(str(payload.get('pwd', '')), _password_version(user)):
        raise TokenError('다시 로그인해 주세요.')  # 비밀번호가 바뀌었거나 예전 형식의 토큰
    return user, payload


def decode_token(token, token_type):
    """토큰을 검증하고 사용자를 돌려준다. 실패하면 TokenError."""
    return _decode(token, token_type)[0]


def _revoke(payload):
    """아직 쓰지 않은 refresh 토큰이면 폐기하고 True. 이미 썼거나 폐기·만료됐으면 False.
    조건부 UPDATE 한 번으로 처리해서 같은 토큰으로 동시에 갱신해도 하나만 성공한다."""
    return RefreshToken.objects.filter(
        jti=str(payload.get('jti', '')), user_id=int(payload['sub']),
        revoked_at__isnull=True, expires_at__gt=timezone.now(),
    ).update(revoked_at=timezone.now()) == 1


def rotate_refresh_token(token):
    """refresh 토큰을 한 번 쓰고 새 access·refresh를 발급한다. 이미 쓴 토큰이면 TokenError."""
    user, payload = _decode(token, 'refresh')
    with transaction.atomic():  # 새 토큰 발급이 실패하면 폐기도 되돌린다
        if not _revoke(payload):
            raise TokenError('이미 사용했거나 로그아웃한 토큰입니다.')
        return issue_tokens(user)


def revoke_refresh_token(token):
    """로그아웃: 이 refresh 토큰만 폐기한다 (다른 기기 로그인은 유지). 잘못된 토큰은 무시한다."""
    try:
        _revoke(_decode(token, 'refresh')[1])
    except TokenError:
        pass


def get_bearer_token(request):
    scheme, _, token = request.headers.get('Authorization', '').partition(' ')
    if scheme.lower() != 'bearer' or not token.strip():
        return None
    return token.strip()


def jwt_required(view):
    """Authorization: Bearer <access 토큰>을 검증해 request.user를 채운다. 실패하면 401."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        token = get_bearer_token(request)
        if token is None:
            return error_response(401, '로그인이 필요합니다.')
        try:
            request.user = decode_token(token, 'access')
        except TokenError as e:
            return error_response(401, str(e))
        return view(request, *args, **kwargs)
    return wrapper
