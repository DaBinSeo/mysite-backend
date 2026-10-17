from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ...forms import AnswerForm
from ...models import Answer, Question
from .jwt_auth import jwt_required
from .utils import (answer_to_dict, error_response, form_error_response,
                    invalid_json_response, method_not_allowed, parse_json)


def _get_answer(answer_id):
    return Answer.objects.select_related('author').filter(pk=answer_id).first()


# ---- /questions/<id>/answers/ ----

@csrf_exempt
def answer_create(request, question_id):
    if request.method != 'POST':
        return method_not_allowed(['POST'])
    return _answer_create(request, question_id)


@jwt_required
def _answer_create(request, question_id):
    question = Question.objects.filter(pk=question_id).first()
    if question is None:
        return error_response(404, '질문을 찾을 수 없습니다.')
    data = parse_json(request)
    if data is None:
        return invalid_json_response()
    form = AnswerForm(data)
    if not form.is_valid():
        return form_error_response(form)
    answer = form.save(commit=False)
    answer.author = request.user
    answer.create_date = timezone.now()
    answer.question = question
    answer.save()
    return JsonResponse(answer_to_dict(answer), status=201)


# ---- /answers/<id>/ ----

@csrf_exempt
def answer_detail(request, answer_id):
    answer = _get_answer(answer_id)
    if answer is None:
        return error_response(404, '답변을 찾을 수 없습니다.')
    if request.method == 'GET':
        return JsonResponse(answer_to_dict(answer))
    if request.method == 'PUT':
        return _answer_modify(request, answer)
    if request.method == 'DELETE':
        return _answer_delete(request, answer)
    return method_not_allowed(['GET', 'PUT', 'DELETE'])


@jwt_required
def _answer_modify(request, answer):
    if request.user != answer.author:
        return error_response(403, '수정권한이 없습니다')
    data = parse_json(request)
    if data is None:
        return invalid_json_response()
    form = AnswerForm(data, instance=answer)
    if not form.is_valid():
        return form_error_response(form)
    answer = form.save(commit=False)
    answer.modify_date = timezone.now()
    answer.save()
    return JsonResponse(answer_to_dict(answer))


@jwt_required
def _answer_delete(request, answer):
    if request.user != answer.author:
        return error_response(403, '삭제권한이 없습니다')
    answer.delete()
    return HttpResponse(status=204)


# ---- /answers/<id>/vote/ ----

@csrf_exempt
def answer_vote(request, answer_id):
    if request.method != 'POST':
        return method_not_allowed(['POST'])
    return _answer_vote(request, answer_id)


@jwt_required
def _answer_vote(request, answer_id):
    answer = _get_answer(answer_id)
    if answer is None:
        return error_response(404, '답변을 찾을 수 없습니다.')
    if request.user == answer.author:
        return error_response(403, '본인이 작성한 글은 추천할수 없습니다')
    answer.voter.add(request.user)
    return JsonResponse({'id': answer.id, 'voter_count': answer.voter.count()})
