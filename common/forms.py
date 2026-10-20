from django.contrib.auth.forms import UserCreationForm

from .models import User


class UserForm(UserCreationForm):
    # 닉네임 형식·중복(대소문자 무시) 검사는 User 모델(validate_nickname, clean)이 맡는다
    class Meta:
        model = User
        fields = ("username", "nickname")
        labels = {"username": "사용자ID"}
