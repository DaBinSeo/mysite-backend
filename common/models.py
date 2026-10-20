from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    """User에 없는 회원 정보(닉네임)를 1:1로 붙인다."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    nickname = models.CharField('닉네임', max_length=20, unique=True)

    def __str__(self):
        return self.nickname
