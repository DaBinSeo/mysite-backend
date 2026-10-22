"""로그인 시도 제한: 같은 계정+IP로 LOGIN_FAILURE_LIMIT번 연속 틀리면 LOGIN_LOCK_MINUTES분 동안 막는다."""
import ipaddress
import math
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import LoginFailure


def get_client_ip(request):
    """게이트웨이(nginx)가 덮어쓰는 X-Real-IP → 없으면 REMOTE_ADDR.
    X-Forwarded-For는 클라이언트가 넣은 값이 앞에 남아 위조할 수 있으므로 쓰지 않는다."""
    for ip in (request.headers.get('X-Real-IP'), request.META.get('REMOTE_ADDR')):
        try:
            return str(ipaddress.ip_address((ip or '').strip()))  # IP 형식이 아닌 값은 버린다
        except ValueError:
            continue
    return ''


def _lock_window():
    return timedelta(minutes=settings.LOGIN_LOCK_MINUTES)


def locked_seconds(username, ip):
    """잠겨 있으면 남은 초, 아니면 0."""
    locked_until = (LoginFailure.objects.filter(username=username, ip=ip, locked_until__gt=timezone.now())
                    .values_list('locked_until', flat=True).first())
    if locked_until is None:
        return 0
    return math.ceil((locked_until - timezone.now()).total_seconds())


def record_failure(username, ip):
    """실패를 하나 늘린다. 이번 실패로 잠겼으면 남은 초, 아니면 0."""
    now = timezone.now()
    with transaction.atomic():
        # 마지막 실패에서 잠금 시간만큼 지난 기록은 지운다 (잠금이 풀린 계정은 처음부터 다시 센다)
        LoginFailure.objects.filter(last_failed_at__lt=now - _lock_window()).delete()
        row, _ = LoginFailure.objects.select_for_update().get_or_create(
            username=username, ip=ip, defaults={'last_failed_at': now})
        row.failures += 1
        row.last_failed_at = now
        if row.failures >= settings.LOGIN_FAILURE_LIMIT:
            row.locked_until = now + _lock_window()
        row.save()
    return math.ceil(_lock_window().total_seconds()) if row.locked_until else 0


def reset_failures(username, ip):
    LoginFailure.objects.filter(username=username, ip=ip).delete()
