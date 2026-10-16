# mysite

「점프 투 장고」 튜토리얼을 따라 만드는 Django 질문/답변 게시판(Pybo) 학습 프로젝트.
Django 6.1 / Python 3.14 / uv / SQLite. 앱: `pybo`(게시판), `common`(로그인·회원가입).

## 명령어
- 개발 서버: `uv run python manage.py runserver`
- 마이그레이션: `uv run python manage.py makemigrations` → `uv run python manage.py migrate`
- 테스트: `uv run python manage.py test`

## 작업 규칙
- 모든 답변과 문서는 한국어로 작성한다.
- **코드를 수정하기 전에 반드시 수정 계획을 먼저 보여주고 승인을 받는다.** 계획에는 원인, 수정할 파일과 줄, 변경 내용(코드), 확인 방법을 포함한다. 사용자가 "수정해줘"처럼 명시적으로 요청한 경우에만 바로 적용한다.
- **코드나 설정을 수정하는 작업을 마치면 개발일지를 갱신한다.** `.claude/agents/devlog-writer.md`의 형식을 따라 `devlog/YYYY-MM-DD.md`(Asia/Seoul 기준 오늘 날짜)에 내용을 추가하고, `devlog/README.md` 목차도 갱신한다. 이미 있는 항목은 중복하지 않고, 해결된 이슈는 "해결됨"으로, 할 일은 `[x]`로 표시한다. 질문에 답만 한 경우에는 갱신하지 않는다.
- 튜토리얼 진도를 벗어나는 큰 리팩터링이나 새 라이브러리 도입은 제안만 하고 임의로 적용하지 않는다.

## 주의사항
- git 저장소(`main` 브랜치)다. 커밋은 사용자가 요청할 때만 한다. 여러 파일을 수정하거나 파일을 삭제하기 전에는 반드시 확인을 받는다.
- `db.sqlite3`, `static/bootstrap.min.*`은 직접 수정하지 않는다.
