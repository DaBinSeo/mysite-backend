from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

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
