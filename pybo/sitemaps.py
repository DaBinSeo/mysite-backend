from django.contrib.sitemaps import Sitemap

from .models import Question


# 검색엔진용 사이트맵(/sitemap.xml). 주소는 API가 아니라 frontend(React)의 화면 경로다
class StaticSitemap(Sitemap):
    def items(self):
        return ['/questions']

    def location(self, item):
        return item


class QuestionSitemap(Sitemap):
    def items(self):
        return Question.objects.only('id', 'create_date', 'modify_date').order_by('-create_date')

    def location(self, question):
        return f'/questions/{question.id}'

    def lastmod(self, question):
        return question.modify_date or question.create_date


sitemaps = {'static': StaticSitemap, 'questions': QuestionSitemap}
