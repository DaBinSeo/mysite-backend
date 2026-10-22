import nh3
from markdown_it import MarkdownIt

# CommonMark 파서. 중첩 괄호 같은 악의적 입력에도 처리 시간이 길이에 거의 비례한다
# (예전 markdown 패키지는 '[' 4천 개에 5초가 넘게 걸렸다)
# breaks: 줄바꿈을 <br>로 바꾼다(예전 nl2br 확장). 코드블록(```)은 CommonMark 기본 기능이다.
_md = MarkdownIt('commonmark', {'breaks': True, 'html': True})


def render_markdown(value):
    """마크다운을 HTML로 바꾼 뒤 nh3로 위험한 태그·속성(<script>, onerror, javascript: 등)을 제거한다."""
    return nh3.clean(_md.render(value))
