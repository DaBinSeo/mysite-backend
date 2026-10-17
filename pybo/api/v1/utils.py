import json

from django.http import JsonResponse

from ...markdown_utils import render_markdown


# ---- 응답 헬퍼 ----

def error_response(status, detail, errors=None):
    body = {'detail': detail}
    if errors is not None:
        body['errors'] = errors
    return JsonResponse(body, status=status)


def form_error_response(form):
    """폼 오류를 {필드: [메시지, ...]} 형태로 돌려준다. 필드와 무관한 오류는 '__all__'에 담긴다."""
    errors = {
        field: [e['message'] for e in field_errors]
        for field, field_errors in form.errors.get_json_data().items()
    }
    return error_response(400, '입력값을 확인해 주세요.', errors)


def method_not_allowed(allowed):
    response = error_response(405, '허용되지 않은 요청 방식입니다.')
    response['Allow'] = ', '.join(allowed)
    return response


def not_found(request, *args, **kwargs):
    return error_response(404, '요청한 API를 찾을 수 없습니다.')


def parse_json(request):
    """요청 본문(JSON 객체)을 dict로 돌려준다. 형식이 잘못되면 None."""
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def invalid_json_response():
    return error_response(400, 'JSON 형식이 올바르지 않습니다.')


# ---- 직렬화 ----

def _iso(value):
    return value.isoformat() if value else None


def user_to_dict(user):
    return {'id': user.id, 'username': user.username, 'email': user.email}


def answer_to_dict(answer):
    return {
        'id': answer.id,
        'question_id': answer.question_id,
        'content': answer.content,
        'content_html': render_markdown(answer.content),
        'author': answer.author.username,
        'create_date': _iso(answer.create_date),
        'modify_date': _iso(answer.modify_date),
        'voter_count': answer.voter.count(),
    }


def question_summary(question):
    """목록용: answer_count는 쿼리에서 annotate한 값을 쓴다."""
    return {
        'id': question.id,
        'subject': question.subject,
        'author': question.author.username,
        'create_date': _iso(question.create_date),
        'answer_count': question.answer_count,
    }


def question_to_dict(question):
    """상세용: 본문, 추천 수, 답변 목록까지 포함한다."""
    answers = question.answer_set.select_related('author').order_by('create_date')
    return {
        'id': question.id,
        'subject': question.subject,
        'content': question.content,
        'content_html': render_markdown(question.content),
        'author': question.author.username,
        'create_date': _iso(question.create_date),
        'modify_date': _iso(question.modify_date),
        'voter_count': question.voter.count(),
        'answer_count': len(answers),
        'answers': [answer_to_dict(a) for a in answers],
    }
