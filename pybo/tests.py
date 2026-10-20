from datetime import timedelta

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .models import Answer, Question

API = '/api/v1'
PASSWORD = 'pybo-test-pass-123'


class ApiTestCase(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('author', 'author@example.com', PASSWORD)
        self.other = User.objects.create_user('other', 'other@example.com', PASSWORD)
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
        self.assertEqual(res.json()['author'], 'other')
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
        self.assertEqual(User.objects.get(username='newbie').profile.nickname, '새내기')

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

    def test_me_nickname_fallback(self):
        # 프로필이 없는 기존 회원은 닉네임 자리에 사용자ID를 준다
        body = self.call('get', '/auth/me/', user=self.author).json()
        self.assertEqual(body['nickname'], 'author')
        self.assertNotIn('email', body)

    def test_password_rules(self):
        body = self.client.get(f'{API}/auth/password-rules/').json()
        self.assertEqual(len(body['rules']), 4)
