import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import Profile

NICKNAME_PATTERN = re.compile(r'[가-힣A-Za-z0-9]+')
HANGUL_PATTERN = re.compile(r'[가-힣]')


class UserForm(UserCreationForm):
    nickname = forms.CharField(
        label="닉네임", max_length=20,
        help_text="한글·영문·숫자만 쓸 수 있습니다. 한글이 들어가면 2자, 아니면 3자 이상입니다.")

    class Meta:
        model = User
        fields = ("username", "password1", "password2")
        labels = {"username": "사용자ID"}

    def clean_nickname(self):
        nickname = self.cleaned_data["nickname"]
        if not NICKNAME_PATTERN.fullmatch(nickname):
            raise forms.ValidationError("닉네임에는 한글(완성형)·영문·숫자만 쓸 수 있습니다. 공백·특수문자는 안 됩니다.")
        min_length = 2 if HANGUL_PATTERN.search(nickname) else 3
        if len(nickname) < min_length:
            raise forms.ValidationError("닉네임은 한글이 들어가면 2자, 영문·숫자만이면 3자 이상이어야 합니다.")
        if Profile.objects.filter(nickname__iexact=nickname).exists():
            raise forms.ValidationError("이미 사용 중인 닉네임입니다.")
        return nickname

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Profile.objects.create(user=user, nickname=self.cleaned_data["nickname"])
        return user
