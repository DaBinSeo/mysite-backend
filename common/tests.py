from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import LoginFailure

User = get_user_model()


class UserModelTests(TestCase):
    def test_user_has_nickname_but_no_first_or_last_name(self):
        field_names = {f.name for f in User._meta.get_fields()}
        self.assertIn('nickname', field_names)
        self.assertNotIn('first_name', field_names)
        self.assertNotIn('last_name', field_names)

    def test_nickname_validated_on_model(self):
        user = User(username='tester', nickname='a b')
        user.set_password('Strong-pass-987')
        with self.assertRaises(ValidationError) as cm:
            user.full_clean()
        self.assertIn('nickname', cm.exception.message_dict)


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'Strong-pass-987',
                                                   nickname='관리자')
        self.client.force_login(self.admin)

    def test_admin_pages_render(self):
        for path in ['/admin/common/user/', '/admin/common/user/add/',
                     f'/admin/common/user/{self.admin.pk}/change/', '/admin/common/user/?q=관리']:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_admin_add_user_with_nickname(self):
        res = self.client.post('/admin/common/user/add/', {
            'username': 'staffer', 'nickname': '스태프', 'usable_password': 'true',
            'password1': 'Strong-pass-987', 'password2': 'Strong-pass-987'})
        self.assertEqual(res.status_code, 302)
        self.assertEqual(User.objects.get(username='staffer').nickname, '스태프')

    def test_admin_rejects_nickname_differing_only_in_case(self):
        User.objects.create_user('tom', nickname='Tom')
        res = self.client.post('/admin/common/user/add/', {
            'username': 'tom2', 'nickname': 'tom', 'usable_password': 'true',
            'password1': 'Strong-pass-987', 'password2': 'Strong-pass-987'})
        self.assertEqual(res.status_code, 200)
        self.assertIn('nickname', res.context['adminform'].form.errors)
        self.assertFalse(User.objects.filter(username='tom2').exists())


class LoginThrottleTests(TestCase):
    PASSWORD = 'Strong-pass-987'

    def setUp(self):
        self.user = User.objects.create_user('throttle', password=self.PASSWORD, nickname='제한')
        User.objects.create_user('neighbor', password=self.PASSWORD, nickname='이웃')

    def login(self, password, username='throttle', ip='10.0.0.1'):
        return self.client.post('/api/v1/auth/login/', {'username': username, 'password': password},
                                content_type='application/json', headers={'X-Real-IP': ip})

    def fail(self, times, **kwargs):
        for _ in range(times):
            self.login('wrong-password', **kwargs)

    def test_locked_after_five_failures(self):
        self.fail(3)
        self.assertEqual(self.login('wrong-password').status_code, 400)  # 4번째까지는 일반 오류
        res = self.login('wrong-password')  # 5번째 실패에서 바로 잠김
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res['Retry-After'], '900')
        self.assertIn('15분 후', res.json()['errors']['__all__'][0])
        # 잠긴 동안은 비밀번호가 맞아도 막는다
        self.assertEqual(self.login(self.PASSWORD).status_code, 429)

    def test_lock_is_per_account_and_ip(self):
        self.fail(5)
        self.assertEqual(self.login(self.PASSWORD, ip='10.0.0.2').status_code, 200)  # 다른 IP
        self.assertEqual(self.login(self.PASSWORD, username='neighbor').status_code, 200)  # 다른 계정

    def test_unlocked_after_lock_time(self):
        self.fail(5)
        past = timezone.now() - timedelta(minutes=15, seconds=1)
        LoginFailure.objects.update(last_failed_at=past, locked_until=past)
        self.assertEqual(self.login(self.PASSWORD).status_code, 200)
        self.assertFalse(LoginFailure.objects.exists())

    def test_success_resets_and_blank_password_not_counted(self):
        self.fail(4)
        self.assertEqual(self.login(self.PASSWORD).status_code, 200)
        self.assertFalse(LoginFailure.objects.exists())
        for _ in range(5):
            self.login('')
        self.assertFalse(LoginFailure.objects.exists())

    def test_old_failures_are_cleaned_up(self):
        self.fail(3)
        LoginFailure.objects.update(last_failed_at=timezone.now() - timedelta(minutes=16))
        self.fail(1, username='neighbor')
        self.assertEqual(list(LoginFailure.objects.values_list('username', 'failures')), [('neighbor', 1)])

    def test_admin_login_is_throttled(self):
        User.objects.create_superuser('boss', password=self.PASSWORD, nickname='관리')
        for _ in range(5):
            self.client.post('/admin/login/', {'username': 'boss', 'password': 'wrong-password'},
                             headers={'X-Real-IP': '10.0.0.9'})
        res = self.client.post('/admin/login/', {'username': 'boss', 'password': self.PASSWORD},
                               headers={'X-Real-IP': '10.0.0.9'})
        self.assertContains(res, '분 후에 다시 시도하세요')
        self.assertNotIn('_auth_user_id', self.client.session)
        # API와 같은 기록을 쓰므로 같은 계정+IP는 API 로그인도 막힌다
        self.assertEqual(self.login(self.PASSWORD, username='boss', ip='10.0.0.9').status_code, 429)

    def test_admin_login_by_non_staff_with_right_password_not_counted(self):
        for _ in range(6):
            self.client.post('/admin/login/', {'username': 'throttle', 'password': self.PASSWORD},
                             headers={'X-Real-IP': '10.0.0.1'})
        self.assertFalse(LoginFailure.objects.exists())
        self.assertEqual(self.login(self.PASSWORD).status_code, 200)

    def test_invalid_ip_header_falls_back_to_remote_addr(self):
        self.fail(5, ip='not-an-ip')
        self.assertEqual(list(LoginFailure.objects.values_list('ip', flat=True)), ['127.0.0.1'])
