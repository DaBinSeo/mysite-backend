from datetime import timedelta
from functools import wraps

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .utils import error_response

User = get_user_model()


class TokenError(Exception):
    pass


def _encode(user, token_type, lifetime):
    now = timezone.now()
    payload = {
        'sub': str(user.id),
        'type': token_type,
        'iat': now,
        'exp': now + lifetime,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user):
    return _encode(user, 'access', timedelta(minutes=settings.JWT_ACCESS_LIFETIME_MINUTES))


def create_refresh_token(user):
    return _encode(user, 'refresh', timedelta(days=settings.JWT_REFRESH_LIFETIME_DAYS))


def issue_tokens(user):
    return {'access': create_access_token(user), 'refresh': create_refresh_token(user)}


def decode_token(token, token_type):
    """토큰을 검증하고 사용자를 돌려준다. 실패하면 TokenError."""
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
        return User.objects.get(pk=int(payload['sub']), is_active=True)
    except (User.DoesNotExist, ValueError):
        raise TokenError('사용자를 찾을 수 없습니다.')


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
