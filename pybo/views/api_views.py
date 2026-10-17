from django.http import JsonResponse

from ..models import Question

def question_list(request):
    questions = Question.objects.select_related('author').order_by('-create_date')[:10]
    data = [
        {
            'id': q.id,
            'subject': q.subject,
            'author': q.author.username,
            'create_date': q.create_date.isoformat(),
        }
        for q in questions
    ]
    return JsonResponse({'questions': data})
