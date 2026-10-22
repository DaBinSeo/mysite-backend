import time
from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.models import RefreshToken
from .markdown_utils import render_markdown
from .models import CONTENT_MAX_LENGTH, Answer, Question

User = get_user_model()

API = '/api/v1'
PASSWORD = 'pybo-test-pass-123'


class ApiTestCase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('author', 'author@example.com', PASSWORD, nickname='글쓴이')
        self.other = User.objects.create_user('other', 'other@example.com', PASSWORD, nickname='다른사람')
        self.question = Question.objects.create(
            author=self.author, subject='장고 질문', content='본문', create_date=timezone.now())
        self.answer = Answer.objects.create(
            author=self.author, question=self.question, content='답변', create_date=timezone.now())

    def token(self, user):
        res = self.client.post(f'{API}/auth/login/', {'username': user.username, 'password': PASSWORD},
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        return res.json()

    def call(self, method, path, data=None, user=None, token=None):
        headers = {}
        if user is not None:
            token = self.token(user)['access']
        if token is not None:
            headers['Authorization'] = f'Bearer {token}'
        return getattr(self.client, method)(f'{API}{path}', data, content_type='application/json',
                                            headers=headers)


class QuestionReadTests(ApiTestCase):
    def test_list_pagination_and_answer_count(self):
        for i in range(11):
            Question.objects.create(author=self.other, subject=f'q{i}', content='c',
                                    create_date=timezone.now() + timedelta(seconds=i + 1))
        res = self.client.get(f'{API}/questions/')
        body = res.json()
        self.assertEqual(body['count'], 12)
        self.assertEqual(body['num_pages'], 2)
        self.assertEqual(len(body['results']), 10)
        self.assertEqual(body['results'][0]['subject'], 'q10')  # 최신순

        page2 = self.client.get(f'{API}/questions/?page=2').json()
        self.assertEqual(page2['start_index'], 11)
        self.assertEqual(page2['results'][-1]['answer_count'], 1)

    def test_search_includes_answer_content_without_duplicates(self):
        Answer.objects.create(author=self.other, question=self.question, content='답변',
                              create_date=timezone.now())
        body = self.client.get(f'{API}/questions/', {'kw': '답변'}).json()
        self.assertEqual(body['count'], 1)
        self.assertEqual(body['results'][0]['id'], self.question.id)

    def test_author_shown_as_nickname(self):
        Answer.objects.create(author=self.other, question=self.question, content='두번째',
                              create_date=timezone.now() + timedelta(seconds=1))
        body = self.client.get(f'{API}/questions/{self.question.id}/').json()
        self.assertEqual((body['author'], body['author_id']), ('글쓴이', self.author.id))
        self.assertEqual([a['author'] for a in body['answers']], ['글쓴이', '다른사람'])
        self.assertEqual(self.client.get(f'{API}/questions/').json()['results'][0]['author'], '글쓴이')

    def test_search_author_by_nickname_only(self):
        self.assertEqual(self.client.get(f'{API}/questions/', {'kw': '쓴이'}).json()['count'], 1)
        self.assertEqual(self.client.get(f'{API}/questions/', {'kw': 'author'}).json()['count'], 0)

    def test_detail_includes_answers_and_sanitized_html(self):
        self.question.content = '**굵게**<script>alert(1)</script>'
        self.question.save()
        body = self.client.get(f'{API}/questions/{self.question.id}/').json()
        self.assertEqual(body['answer_count'], 1)
        self.assertEqual(body['answers'][0]['content'], '답변')
        self.assertIn('<strong>굵게</strong>', body['content_html'])
        self.assertNotIn('<script>', body['content_html'])

    def test_detail_query_count_does_not_grow_with_answers(self):
        path = f'{API}/questions/{self.question.id}/'
        with CaptureQueriesContext(connection) as one_answer:
            self.client.get(path)
        for i in range(5):
            answer = Answer.objects.create(author=self.author, question=self.question, content=f'a{i}',
                                           create_date=timezone.now() + timedelta(seconds=i + 1))
            answer.voter.add(self.other)
        with CaptureQueriesContext(connection) as six_answers:
            body = self.client.get(path).json()
        self.assertEqual(len(six_answers), len(one_answer))  # 답변이 늘어도 쿼리 수는 그대로
        self.assertEqual([a['voter_count'] for a in body['answers']], [0, 1, 1, 1, 1, 1])

    def test_unknown_question_and_path_return_json_404(self):
        self.assertEqual(self.client.get(f'{API}/questions/9999/').json()['detail'], '질문을 찾을 수 없습니다.')
        res = self.client.get(f'{API}/nothing/')
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res['Content-Type'], 'application/json')


class QuestionWriteTests(ApiTestCase):
    def test_create_requires_token(self):
        res = self.call('post', '/questions/', {'subject': 's', 'content': 'c'})
        self.assertEqual(res.status_code, 401)

    def test_create_with_token(self):
        res = self.call('post', '/questions/', {'subject': '새 질문', 'content': '내용'}, user=self.other)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['author'], '다른사람')
        self.assertEqual(res.json()['author_id'], self.other.id)
        self.assertTrue(Question.objects.filter(subject='새 질문', author=self.other).exists())

    def test_create_with_empty_subject_returns_errors(self):
        res = self.call('post', '/questions/', {'subject': '', 'content': '내용'}, user=self.other)
        self.assertEqual(res.status_code, 400)
        self.assertIn('subject', res.json()['errors'])

    def test_invalid_json(self):
        token = self.token(self.other)['access']
        res = self.client.post(f'{API}/questions/', 'not-json', content_type='application/json',
                               headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(res.status_code, 400)

    def test_modify_only_by_author(self):
        path = f'/questions/{self.question.id}/'
        data = {'subject': '수정됨', 'content': '수정 본문'}
        self.assertEqual(self.call('put', path, data, user=self.other).status_code, 403)
        res = self.call('put', path, data, user=self.author)
        self.assertEqual(res.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.subject, '수정됨')
        self.assertIsNotNone(self.question.modify_date)

    def test_delete_only_by_author(self):
        path = f'/questions/{self.question.id}/'
        self.assertEqual(self.call('delete', path, user=self.other).status_code, 403)
        self.assertEqual(self.call('delete', path, user=self.author).status_code, 204)
        self.assertFalse(Question.objects.filter(pk=self.question.id).exists())

    def test_vote(self):
        path = f'/questions/{self.question.id}/vote/'
        res = self.call('post', path, user=self.author)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()['detail'], '본인이 작성한 글은 추천할수 없습니다')
        self.call('post', path, user=self.other)
        res = self.call('post', path, user=self.other)
        self.assertEqual(res.json()['voter_count'], 1)  # 여러 번 눌러도 1번만

    def test_method_not_allowed(self):
        res = self.client.get(f'{API}/questions/{self.question.id}/vote/')
        self.assertEqual(res.status_code, 405)


class AnswerTests(ApiTestCase):
    def test_create(self):
        path = f'/questions/{self.question.id}/answers/'
        self.assertEqual(self.call('post', path, {'content': '새 답변'}).status_code, 401)
        res = self.call('post', path, {'content': '새 답변'}, user=self.other)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['question_id'], self.question.id)
        self.assertEqual(self.call('post', path, {'content': ''}, user=self.other).status_code, 400)

    def test_get_modify_delete_vote(self):
        path = f'/answers/{self.answer.id}/'
        self.assertEqual(self.client.get(f'{API}{path}').json()['content'], '답변')
        self.assertEqual(self.call('put', path, {'content': 'x'}, user=self.other).status_code, 403)
        res = self.call('put', path, {'content': '수정 답변'}, user=self.author)
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.json()['modify_date'])

        self.assertEqual(self.call('post', f'{path}vote/', user=self.author).status_code, 403)
        self.assertEqual(self.call('post', f'{path}vote/', user=self.other).json()['voter_count'], 1)

        self.assertEqual(self.call('delete', path, user=self.other).status_code, 403)
        self.assertEqual(self.call('delete', path, user=self.author).status_code, 204)
        self.assertFalse(Answer.objects.filter(pk=self.answer.id).exists())


class ContentLimitTests(ApiTestCase):
    def test_question_content_max_length(self):
        data = {'subject': '긴 질문', 'content': '가' * CONTENT_MAX_LENGTH}
        self.assertEqual(self.call('post', '/questions/', data, user=self.other).status_code, 201)
        data['content'] += '가'
        res = self.call('post', '/questions/', data, user=self.other)
        self.assertEqual(res.status_code, 400)
        self.assertIn('content', res.json()['errors'])
        res = self.call('put', f'/questions/{self.question.id}/', data, user=self.author)
        self.assertEqual(res.status_code, 400)

    def test_answer_content_max_length(self):
        path = f'/questions/{self.question.id}/answers/'
        res = self.call('post', path, {'content': 'a' * (CONTENT_MAX_LENGTH + 1)}, user=self.other)
        self.assertEqual(res.status_code, 400)
        self.assertIn('content', res.json()['errors'])
        res = self.call('put', f'/answers/{self.answer.id}/', {'content': 'a' * (CONTENT_MAX_LENGTH + 1)},
                        user=self.author)
        self.assertEqual(res.status_code, 400)


class MarkdownTests(ApiTestCase):
    def test_content_html_is_rendered_on_save(self):
        res = self.call('put', f'/answers/{self.answer.id}/', {'content': '**수정**'}, user=self.author)
        self.assertIn('<strong>수정</strong>', res.json()['content_html'])
        self.answer.refresh_from_db()
        self.assertIn('<strong>수정</strong>', self.answer.content_html)

        self.question.content = '*기울임*'
        self.question.save(update_fields=['content'])  # content만 지정해도 content_html이 함께 저장된다
        self.question.refresh_from_db()
        self.assertIn('<em>기울임</em>', self.question.content_html)

    def test_line_breaks_code_and_sanitizing(self):
        html = render_markdown('줄1\n줄2\n\n```py\nx = [1]\n```\n[a](javascript:alert(1)) '
                               '<a href="javascript:alert(2)">b</a> <img src=x onerror=alert(3)>')
        self.assertIn('줄1<br>', html)
        self.assertIn('<pre><code>x = [1]\n</code></pre>', html)
        self.assertNotIn('href="javascript', html)  # 마크다운 링크는 글자로 남고, HTML 링크는 href가 지워진다
        self.assertNotIn('onerror', html)

    def test_worst_case_input_renders_within_one_second(self):
        n = CONTENT_MAX_LENGTH
        for text in ['[' * n, '![' * (n // 2), '[a' * (n // 2), '[a][' * (n // 4), '[x](' * (n // 4),
                     '[' * (n // 2) + ']' * (n // 2), '*_' * (n // 2), '>' * n, '`a' * (n // 2)]:
            start = time.perf_counter()
            render_markdown(text)
            self.assertLess(time.perf_counter() - start, 1, text[:4])


class AuthTests(ApiTestCase):
    def test_login_failure(self):
        res = self.client.post(f'{API}/auth/login/', {'username': 'author', 'password': 'wrong'},
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('__all__', res.json()['errors'])

    def test_me_and_refresh(self):
        tokens = self.token(self.author)
        self.assertEqual(self.call('get', '/auth/me/', token=tokens['access']).json()['username'], 'author')
        res = self.client.post(f'{API}/auth/refresh/', {'refresh': tokens['refresh']},
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.call('get', '/auth/me/', token=res.json()['access']).status_code, 200)

    def refresh(self, token):
        return self.client.post(f'{API}/auth/refresh/', {'refresh': token}, content_type='application/json')

    def test_refresh_rotates_and_old_token_is_rejected(self):
        old = self.token(self.author)['refresh']
        res = self.refresh(old)
        self.assertEqual(res.status_code, 200)
        new = res.json()['refresh']
        self.assertNotEqual(new, old)
        res = self.refresh(old)  # 이미 쓴 토큰
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['detail'], '이미 사용했거나 로그아웃한 토큰입니다.')
        self.assertEqual(self.refresh(new).status_code, 200)  # 재사용 시도가 있어도 새 토큰은 그대로 쓸 수 있다

    def test_logout_revokes_only_this_device(self):
        pc, phone = self.token(self.author), self.token(self.author)
        res = self.client.post(f'{API}/auth/logout/', {'refresh': pc['refresh']}, content_type='application/json')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(self.refresh(pc['refresh']).status_code, 401)
        self.assertEqual(self.refresh(phone['refresh']).status_code, 200)
        # 잘못된 토큰이나 빈 요청도 오류 없이 끝난다
        for body in [{'refresh': 'abc'}, {}]:
            res = self.client.post(f'{API}/auth/logout/', body, content_type='application/json')
            self.assertEqual(res.status_code, 204)

    def test_expired_refresh_records_are_cleaned_up(self):
        self.token(self.author)
        RefreshToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.token(self.author)  # 새로 발급할 때 만료된 기록을 지운다
        self.assertEqual(RefreshToken.objects.count(), 1)

    def test_password_change_invalidates_all_tokens(self):
        tokens = self.token(self.author)
        self.author.set_password('Changed-pass-456')
        self.author.save()
        res = self.call('get', '/auth/me/', token=tokens['access'])
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['detail'], '다시 로그인해 주세요.')
        self.assertEqual(self.refresh(tokens['refresh']).status_code, 401)

    def test_token_without_password_version_is_rejected(self):
        # 이번 변경 전에 발급한 형식(pwd·jti 없음)은 더 이상 받지 않는다
        now = timezone.now()
        for token_type in ['access', 'refresh']:
            token = jwt.encode({'sub': str(self.author.id), 'type': token_type, 'iat': now,
                                'exp': now + timedelta(minutes=5)}, settings.SECRET_KEY, algorithm='HS256')
            res = (self.call('get', '/auth/me/', token=token) if token_type == 'access'
                   else self.refresh(token))
            self.assertEqual(res.status_code, 401, token_type)

    def test_refresh_token_cannot_be_used_as_access(self):
        tokens = self.token(self.author)
        self.assertEqual(self.call('get', '/auth/me/', token=tokens['refresh']).status_code, 401)

    def test_expired_and_invalid_tokens(self):
        past = timezone.now() - timedelta(hours=1)
        expired = jwt.encode({'sub': str(self.author.id), 'type': 'access', 'iat': past, 'exp': past},
                             settings.SECRET_KEY, algorithm='HS256')
        res = self.call('get', '/auth/me/', token=expired)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.json()['detail'], '토큰이 만료되었습니다.')
        self.assertEqual(self.call('get', '/auth/me/', token='abc.def.ghi').status_code, 401)
        forged = jwt.encode({'sub': str(self.author.id), 'type': 'access',
                             'exp': timezone.now() + timedelta(minutes=5)}, 'wrong-key' * 4, algorithm='HS256')
        self.assertEqual(self.call('get', '/auth/me/', token=forged).status_code, 401)

    def test_signup(self):
        data = {'username': 'newbie', 'password1': 'Strong-pass-987', 'password2': 'Strong-pass-987',
                'nickname': '새내기'}
        res = self.client.post(f'{API}/auth/signup/', data, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        self.assertIn('access', res.json())
        self.assertEqual(res.json()['user']['nickname'], '새내기')
        self.assertEqual(User.objects.get(username='newbie').nickname, '새내기')

        bad = {**data, 'username': 'newbie2', 'nickname': 'newbie2', 'password1': '123', 'password2': '123'}
        res = self.client.post(f'{API}/auth/signup/', bad, content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('password2', res.json()['errors'])

    def test_signup_nickname_rules(self):
        base = {'password1': 'Strong-pass-987', 'password2': 'Strong-pass-987'}
        valid = ['가나', 'abc', 'ab1', '홍길동99', 'a가']
        invalid = ['', '가', 'ab', '12', 'ab c', 'ab!', '닉_네임', 'ㄱㄴ', 'a' * 21]
        for i, nickname in enumerate(valid):
            res = self.client.post(f'{API}/auth/signup/', {**base, 'username': f'ok{i}', 'nickname': nickname},
                                   content_type='application/json')
            self.assertEqual(res.status_code, 201, nickname)
        for i, nickname in enumerate(invalid):
            res = self.client.post(f'{API}/auth/signup/', {**base, 'username': f'bad{i}', 'nickname': nickname},
                                   content_type='application/json')
            self.assertEqual(res.status_code, 400, nickname)
            self.assertIn('nickname', res.json()['errors'])
        # 대소문자만 다른 닉네임도 중복으로 본다
        res = self.client.post(f'{API}/auth/signup/', {**base, 'username': 'dup', 'nickname': 'ABC'},
                               content_type='application/json')
        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.filter(username='dup').exists())

    def test_me_returns_nickname(self):
        body = self.call('get', '/auth/me/', user=self.author).json()
        self.assertEqual(body['nickname'], '글쓴이')
        self.assertNotIn('email', body)

    def test_password_rules(self):
        body = self.client.get(f'{API}/auth/password-rules/').json()
        self.assertEqual(len(body['rules']), 4)


class SitemapTests(ApiTestCase):
    def test_sitemap_lists_question_pages(self):
        res = self.client.get('/sitemap.xml')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/xml')
        body = res.content.decode()
        self.assertIn('<loc>http://testserver/questions</loc>', body)
        self.assertIn(f'<loc>http://testserver/questions/{self.question.id}</loc>', body)
        self.assertIn('<lastmod>', body)
