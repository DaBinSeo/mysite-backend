from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import password_validators_help_texts
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from common.forms import UserForm
from .jwt_auth import TokenError, create_access_token, decode_token, issue_tokens, jwt_required
from .utils import (error_response, form_error_response, invalid_json_response,
                    method_not_allowed, parse_json, user_to_dict)


def _token_response(user, status=200):
    return JsonResponse({**issue_tokens(user), 'user': user_to_dict(user)}, status=status)


@csrf_exempt
def signup(request):
    if request.method != 'POST':
        return method_not_allowed(['POST'])
    data = parse_json(request)
    if data is None:
        return invalid_json_response()
    form = UserForm(data)
    if not form.is_valid():
        return form_error_response(form)
    user = form.save()
    return _token_response(user, status=201)  # 가입 후 바로 로그인 상태


def password_rules(request):
    """회원가입 화면에 보여 줄 비밀번호 조건 (AUTH_PASSWORD_VALIDATORS 기준)."""
    if request.method != 'GET':
        return method_not_allowed(['GET'])
    return JsonResponse({
        'rules': [str(text) for text in password_validators_help_texts()],
        'confirm_help': str(UserForm().fields['password2'].help_text),
    })


@csrf_exempt
def login(request):
    if request.method != 'POST':
        return method_not_allowed(['POST'])
    data = parse_json(request)
    if data is None:
        return invalid_json_response()
    form = AuthenticationForm(request, data=data)  # 장고 로그인 폼의 검증·오류 문구를 그대로 사용
    if not form.is_valid():
        return form_error_response(form)
    return _token_response(form.get_user())


@csrf_exempt
def refresh(request):
    if request.method != 'POST':
        return method_not_allowed(['POST'])
    data = parse_json(request)
    if data is None:
        return invalid_json_response()
    token = data.get('refresh')
    if not token:
        return error_response(400, 'refresh 토큰이 필요합니다.')
    try:
        user = decode_token(token, 'refresh')
    except TokenError as e:
        return error_response(401, str(e))
    return JsonResponse({'access': create_access_token(user)})


def me(request):
    if request.method != 'GET':
        return method_not_allowed(['GET'])
    return _me(request)


@jwt_required
def _me(request):
    return JsonResponse(user_to_dict(request.user))
