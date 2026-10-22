from django.contrib.auth.password_validation import password_validators_help_texts
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from common.forms import LoginForm, UserForm
from .jwt_auth import TokenError, issue_tokens, jwt_required, revoke_refresh_token, rotate_refresh_token
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
    form = LoginForm(request, data=data)  # 장고 로그인 폼의 검증·오류 문구 + 로그인 시도 제한
    if not form.is_valid():
        response = form_error_response(form)
        if form.has_error('__all__', LoginForm.LOCKED_CODE):
            response.status_code = 429
            response['Retry-After'] = str(form.locked_seconds)
        return response
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
        tokens = rotate_refresh_token(token)  # 쓴 refresh 토큰은 폐기하고 새 refresh 토큰도 준다
    except TokenError as e:
        return error_response(401, str(e))
    return JsonResponse(tokens)


@csrf_exempt
def logout(request):
    """이 기기의 refresh 토큰만 폐기한다. access 토큰은 만료(30분)까지 남지만 프런트가 지운다."""
    if request.method != 'POST':
        return method_not_allowed(['POST'])
    data = parse_json(request)
    if data is None:
        return invalid_json_response()
    token = data.get('refresh')
    if token:
        revoke_refresh_token(str(token))
    return HttpResponse(status=204)


def me(request):
    if request.method != 'GET':
        return method_not_allowed(['GET'])
    return _me(request)


@jwt_required
def _me(request):
    return JsonResponse(user_to_dict(request.user))
