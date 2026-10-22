from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm as BaseUserChangeForm

from .forms import AdminLoginForm
from .models import LoginFailure, User

# 관리자 화면 로그인에도 API와 같은 로그인 시도 제한을 건다
admin.site.login_form = AdminLoginForm


class UserChangeForm(BaseUserChangeForm):
    class Meta(BaseUserChangeForm.Meta):
        model = User


class UserAddForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('username', 'nickname')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserAddForm
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('회원 정보', {'fields': ('nickname', 'email')}),
        ('권한', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('주요 일자', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'nickname', 'usable_password', 'password1', 'password2'),
        }),
    )
    list_display = ('username', 'nickname', 'email', 'is_staff')
    search_fields = ('username', 'nickname', 'email')


@admin.register(LoginFailure)
class LoginFailureAdmin(admin.ModelAdmin):
    """잠긴 계정을 확인하고, 삭제해서 바로 풀 수 있다 (추가·수정은 막는다)"""
    list_display = ('username', 'ip', 'failures', 'last_failed_at', 'locked_until')
    search_fields = ('username', 'ip')
    readonly_fields = list_display

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
