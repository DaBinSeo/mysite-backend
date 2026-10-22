from django.db import models
from django.conf import settings

from .markdown_utils import render_markdown

# 본문 최대 글자 수. 이 길이의 최악의 마크다운 입력도 렌더링이 1초 안에 끝난다 (frontend도 같은 값을 쓴다)
CONTENT_MAX_LENGTH = 10000


class RenderContentMixin:
    """저장할 때 content를 렌더링해 content_html에 넣는다.
    QuerySet.update()·bulk_create()처럼 save()를 거치지 않는 방법으로 content를 바꾸면 content_html이 갱신되지 않는다."""

    def save(self, *args, **kwargs):
        self.content_html = render_markdown(self.content)
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'content' in update_fields:
            kwargs['update_fields'] = {*update_fields, 'content_html'}
        super().save(*args, **kwargs)


class Question(RenderContentMixin, models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='author_question')
    subject = models.CharField(max_length=200)
    content = models.TextField(max_length=CONTENT_MAX_LENGTH)
    content_html = models.TextField(blank=True, editable=False)  # 저장할 때 한 번만 렌더링 (조회마다 렌더링하지 않도록)
    create_date = models.DateTimeField()
    modify_date = models.DateTimeField(null=True, blank=True)
    voter = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='voter_question')

    def __str__(self):
        return self.subject

class Answer(RenderContentMixin, models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='author_answer')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    content = models.TextField(max_length=CONTENT_MAX_LENGTH)
    content_html = models.TextField(blank=True, editable=False)  # Question.content_html과 같음
    create_date = models.DateTimeField()
    modify_date = models.DateTimeField(null=True, blank=True)
    voter = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='voter_answer')

    def __str__(self):
        return self.content
