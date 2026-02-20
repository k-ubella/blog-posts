# 텔레그램 한 마디로 티스토리 자동 발행하기 (OpenClaw + Playwright)

> 옵시디언에서 글을 쓰고, GitHub에 push하고, 텔레그램에 "티스토리 올려줘" 한 마디 치면 자동 발행되는 시스템을 구축했습니다.

---

## 왜 만들었나

티스토리는 공식 Open API가 2024년 2월에 종료됐습니다. 외부에서 API 호출로 글을 올리는 방법이 막힌 거죠.

그렇다고 매번 에디터를 열어 복붙하는 건 너무 번거롭습니다. 저는 옵시디언(Obsidian)으로 로컬에서 마크다운으로 글을 쓰는데, 이걸 그대로 티스토리에 올릴 수 없을까 고민했습니다.

결국 **Playwright로 브라우저를 자동화**해서 직접 에디터에 글을 주입하는 방식으로 해결했습니다.

---

## 전체 자동화 흐름

```
[노트북 - 옵시디언]          [GitHub]           [Ubuntu - OpenClaw]      [티스토리]
  글 작성 (.md)       →    git push      →    텔레그램 수신            →  자동 발행
  이미지 붙여넣기          이미지 포함         git pull + 스크립트 실행     이미지 포함
```

각 단계를 정리하면 이렇습니다.

1. 옵시디언에서 마크다운으로 글 작성, 이미지 붙여넣기 (`00_첨부파일/` 폴더에 자동 저장)
2. `git add . && git commit && git push` 로 GitHub에 올리기
3. 텔레그램에서 "티스토리 올려줘" 입력
4. OpenClaw가 메시지를 감지하고 `git pull` + 배포 스크립트 실행
5. Playwright가 티스토리 에디터에 접속해서 글 자동 발행

---

## 핵심 기술 스택

| 역할 | 도구 |
|------|------|
| 마크다운 편집 | Obsidian |
| 파일 동기화 | GitHub (Public 레포) |
| 자동화 트리거 | Telegram + OpenClaw |
| 브라우저 자동화 | Python + Playwright |
| 이미지 호스팅 | GitHub raw URL |

---

## 이미지 처리 방식

티스토리 자동화에서 가장 까다로운 부분이 **이미지 업로드**입니다.

티스토리 에디터는 내부적으로 TinyMCE를 사용하는데, 파일 업로드 인터페이스가 JavaScript로 동적 생성됩니다. 자동화 스크립트로 파일 input을 찾기가 매우 어렵습니다.

**해결책: GitHub raw URL 방식**

이미지를 티스토리에 올리는 대신, GitHub Public 레포의 raw URL을 `<img>` 태그로 직접 삽입합니다.

```
옵시디언 이미지 문법:  ![[Pasted image 20260220145957.png]]
                         ↓  자동 변환
GitHub raw URL:  <img src="https://raw.githubusercontent.com/your-id/blog-posts/main/00_%EC%B2%A8%EB%B6%80%ED%8C%8C%EC%9D%BC/Pasted%20image%2020260220145957.png">
```

별도 업로드 과정이 없어서 훨씬 안정적이고 빠릅니다.

---

## 로그인 방식: 세션 쿠키

비밀번호를 코드에 저장하면 보안 위험이 있습니다. 대신 **최초 1회만 로그인**하고 세션 쿠키를 파일로 저장하는 방식을 사용합니다.

```bash
# 최초 1회만 실행
python3 tistory_login.py
```

실행하면 브라우저가 열리고 카카오 로그인 → 2단계 인증 → `tistory_session.json` 저장. 이후부터는 세션 파일로 자동 로그인됩니다.

> **주의:** `tistory_session.json` 은 반드시 `.gitignore` 에 추가해서 GitHub에 올라가지 않도록 합니다.

---

## 핵심 코드 설명

### 마크다운 → HTML 변환 + 이미지 처리

```python
def github_raw_url(img_name: str) -> Optional[str]:
    """이미지 파일명 → GitHub raw URL 자동 변환"""
    repo_root = Path(__file__).parent
    user   = CONFIG["github_user"]
    repo   = CONFIG["github_repo"]
    branch = CONFIG["github_branch"]

    # 00_첨부파일/, posts/, posts/images/ 순서로 탐색
    candidates = [
        repo_root / "00_첨부파일" / img_name,
        repo_root / "posts" / img_name,
        repo_root / img_name,
    ]
    for c in candidates:
        if c.exists():
            rel = c.resolve().relative_to(repo_root.resolve())
            # 한글·공백 URL 인코딩 처리
            encoded = "/".join(urllib.parse.quote(part) for part in rel.parts)
            return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{encoded}"
    return None
```

한글 파일명이나 공백이 포함된 경우 `urllib.parse.quote()` 로 URL 인코딩합니다.

### TinyMCE 에디터에 본문 주입

```python
injected = await page.evaluate(f"""
    (() => {{
        if (typeof tinymce !== 'undefined') {{
            const ed = tinymce.activeEditor || tinymce.editors[0];
            if (ed) {{
                ed.setContent(`{escaped}`);
                ed.save();
                ed.fire('change');
                return 'tinymce';
            }}
        }}
        return 'not_found';
    }})()
""")
```

티스토리는 TinyMCE 에디터를 사용하므로 `tinymce.activeEditor.setContent()` 로 HTML을 직접 주입합니다.

### 발행 처리

```python
# 완료 버튼 클릭 → 팝업 오픈
await page.click("button.btn.btn-default")
await page.wait_for_timeout(2000)

# 공개 라디오 선택
await page.click("input#open20")
await page.wait_for_timeout(500)

# 발행 버튼
await page.click("button#publish-btn")
```

티스토리 발행 팝업에서 **공개** 라디오 버튼(`input#open20`) 선택 후 발행 버튼을 클릭합니다.

---

## OpenClaw 스킬 등록

텔레그램 자연어 트리거를 등록합니다.

```bash
mkdir -p ~/.openclaw/skills/tistory
```

`~/.openclaw/skills/tistory/SKILL.md` 파일 내용:

```markdown
---
name: tistory_post
description: GitHub에서 최신 마크다운 파일을 가져와 티스토리에 발행합니다
triggers:
  - "티스토리 올려줘"
  - "블로그 발행해줘"
  - "포스팅 해줘"
  - "최신 글 올려줘"
---

## 티스토리 자동 발행

사용자가 티스토리 발행을 요청하면 아래 명령어를 실행하세요:

```bash
cd ~/tistory-bot && PYTHONIOENCODING=utf-8 python3 tistory_playwright.py
```
```

등록 후 텔레그램에서 `refresh skills` 를 입력하면 바로 사용 가능합니다.

---

## 세팅 방법 (처음부터 따라하기)

### 1단계: GitHub 레포 생성

- **Public 레포**로 생성 (이미지 raw URL 접근에 필요)
- 로컬 옵시디언 폴더를 이 레포와 연결

```bash
cd ~/your-obsidian-folder
git init
git remote add origin https://github.com/your-github-id/blog-posts.git
```

### 2단계: Ubuntu 서버에 레포 클론

```bash
git clone https://your-github-id:YOUR_TOKEN@github.com/your-github-id/blog-posts.git ~/tistory-bot
cd ~/tistory-bot
```

### 3단계: Playwright 설치

```bash
pip install playwright
playwright install chromium
playwright install-deps chromium
```

> `python` 명령어가 없을 경우: `sudo apt install python-is-python3`

### 4단계: CONFIG 설정

`tistory_playwright.py` 상단 수정:

```python
CONFIG = {
    "blog_name":     "your-blog-name",   # 티스토리 블로그 이름
    "github_user":   "your-github-id",   # GitHub 사용자명
    "github_repo":   "blog-posts",       # 레포 이름 (Public)
    "github_branch": "main",
}
```

### 5단계: 최초 로그인

```bash
python3 tistory_login.py
```

카카오 2단계 인증까지 마치면 `tistory_session.json` 이 자동 저장됩니다.

### 6단계: 테스트 발행

```bash
# 임시저장으로 먼저 확인
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py --draft --file "posts/테스트.md"

# 정상이면 실제 발행
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py --file "posts/테스트.md"
```

---

## 일상 사용 흐름

세팅이 완료된 이후 글 발행하는 방법:

```bash
# 1. 노트북에서 글 작성 후
git add posts/ 00_첨부파일/
git commit -m "새 글: 글제목"
git push

# 2. 텔레그램에서 입력
# "티스토리 올려줘"
# → 끝! OpenClaw가 나머지 자동 처리
```

---

## 트러블슈팅

### 세션이 만료됐다고 나올 때

세션 쿠키는 일정 기간 후 만료됩니다. 다시 로그인하면 됩니다.

```bash
python3 tistory_login.py
```

### UnicodeDecodeError (인코딩 오류)

Ubuntu 터미널에서 한글 처리 오류가 날 경우:

```bash
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py
```

### git pull 인증 오류

PAT 토큰이 만료되거나 재발급한 경우:

```bash
git remote set-url origin https://your-github-id:NEW_TOKEN@github.com/your-github-id/blog-posts.git
```

> **주의:** PAT 토큰이 `.git/config` 에 저장되므로 `git log` 나 설정 파일에서 노출될 수 있습니다. 노출된 토큰은 즉시 GitHub Settings → Developer settings → Personal access tokens에서 **Revoke** 후 재발급하세요.

### 이미지가 티스토리에 안 보일 때

1. GitHub 레포가 **Public** 인지 확인
2. `00_첨부파일/` 폴더가 git에 포함됐는지 확인

```bash
git ls-files | grep 첨부
```

3. 이미지 파일이 push됐는지 GitHub에서 직접 확인

---

## 보안 체크리스트

- [ ] `tistory_session.json` 이 `.gitignore` 에 포함되어 있는지 확인
- [ ] GitHub 레포는 Public이지만 민감한 파일(토큰, 세션 등)이 올라가지 않았는지 확인
- [ ] PAT 토큰을 코드에 직접 하드코딩하지 않기
- [ ] 노출된 토큰은 즉시 revoke 후 재발급
- [ ] 텔레그램 봇 토큰 타인 공유 금지

---

## 마치며

티스토리 공식 API가 막힌 뒤로 자동화가 어렵다고 생각했는데, Playwright로 브라우저를 직접 제어하니 충분히 가능했습니다.

이미지 업로드를 자동화하려다 막혔을 때 GitHub raw URL로 우회하는 아이디어가 핵심이었습니다. 서버에 이미지를 올릴 필요도 없고, 별도 스토리지 비용도 없습니다.

OpenClaw + 텔레그램 조합 덕분에 이제 터미널을 열 필요도 없습니다. 글 쓰고 push하고 텔레그램에 한 마디면 끝입니다.

전체 코드는 [GitHub 레포](https://github.com/your-github-id/blog-posts)에서 확인하실 수 있습니다.
