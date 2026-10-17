import markdown
import nh3


def render_markdown(value):
    """마크다운을 HTML로 바꾼 뒤 nh3로 위험한 태그·속성(<script>, onerror, javascript: 등)을 제거한다."""
    extensions = ["nl2br", "fenced_code"]
    html = markdown.markdown(value, extensions=extensions)
    return nh3.clean(html)
