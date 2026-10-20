from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ...forms import QuestionForm
from ...models import Question
from .jwt_auth import jwt_required
from .utils import (error_response, form_error_response, invalid_json_response,
                    method_not_allowed, parse_json, question_summary, question_to_dict)

PAGE_SIZE = 10


def _get_question(question_id):
    return Question.objects.select_related('author__profile').filter(pk=question_id).first()


# ---- /questions/ ----

@csrf_exempt
def question_list_create(request):
    if request.method == 'GET':
        return _question_list(request)
    if request.method == 'POST':
        return _question_create(request)
    return method_not_allowed(['GET', 'POST'])


def _question_list(request):
    page = request.GET.get('page', '1')
    kw = request.GET.get('kw', '')  # 검색어
    question_list = (Question.objects.select_related('author__profile')
                     .annotate(answer_count=Count('answer', distinct=True))
                     .order_by('-create_date'))
    if kw:
        question_list = question_list.filter(
            Q(subject__icontains=kw) |  # 제목 검색
            Q(content__icontains=kw) |  # 내용 검색
            Q(answer__content__icontains=kw) |  # 답변 내용 검색
            # 글쓴이는 화면에 보이는 닉네임으로만 검색한다 (사용자ID로 검색하면 가린 ID를 알아낼 수 있다)
            Q(author__profile__nickname__icontains=kw) |  # 질문 글쓴이 검색
            Q(answer__author__profile__nickname__icontains=kw)  # 답변 글쓴이 검색
        ).distinct()
    paginator = Paginator(question_list, PAGE_SIZE)
    page_obj = paginator.get_page(page)
    return JsonResponse({
        'count': paginator.count,
        'page': page_obj.number,
        'num_pages': paginator.num_pages,
        'start_index': page_obj.start_index(),
        'kw': kw,
        'results': [question_summary(q) for q in page_obj],
    })


@jwt_required
def _question_create(request):
    data = parse_json(request)
    if data is None:
        return invalid_json_response()
    form = QuestionForm(data)
    if not form.is_valid():
        return form_error_response(form)
    question = form.save(commit=False)
    question.author = request.user
    question.create_date = timezone.now()
    question.save()
    return JsonResponse(question_to_dict(question), status=201)


# ---- /questions/<id>/ ----

@csrf_exempt
def question_detail(request, question_id):
    question = _get_question(question_id)
    if question is None:
        return error_response(404, '질문을 찾을 수 없습니다.')
    if request.method == 'GET':
        return JsonResponse(question_to_dict(question))
    if request.method == 'PUT':
        return _question_modify(request, question)
    if request.method == 'DELETE':
        return _question_delete(request, question)
    return method_not_allowed(['GET', 'PUT', 'DELETE'])


@jwt_required
def _question_modify(request, question):
    if request.user != question.author:
        return error_response(403, '수정권한이 없습니다.')
    data = parse_json(request)
    if data is None:
        return invalid_json_response()
    form = QuestionForm(data, instance=question)
    if not form.is_valid():
        return form_error_response(form)
    question = form.save(commit=False)
    question.modify_date = timezone.now()
    question.save()
    return JsonResponse(question_to_dict(question))


@jwt_required
def _question_delete(request, question):
    if request.user != question.author:
        return error_response(403, '삭제권한이 없습니다.')
    question.delete()
    return HttpResponse(status=204)


# ---- /questions/<id>/vote/ ----

@csrf_exempt
def question_vote(request, question_id):
    if request.method != 'POST':
        return method_not_allowed(['POST'])
    return _question_vote(request, question_id)


@jwt_required
def _question_vote(request, question_id):
    question = _get_question(question_id)
    if question is None:
        return error_response(404, '질문을 찾을 수 없습니다.')
    if request.user == question.author:
        return error_response(403, '본인이 작성한 글은 추천할수 없습니다')
    question.voter.add(request.user)  # 같은 사용자가 여러 번 눌러도 1번만 집계
    return JsonResponse({'id': question.id, 'voter_count': question.voter.count()})
