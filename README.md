# 🤖 OpenClaw × 티스토리 자동 배포

> 옵시디언에서 마크다운 작성 → GitHub push → 텔레그램 한 마디 → 티스토리 자동 발행

---

## 전체 흐름

```
노트북 (옵시디언)         GitHub              Ubuntu (OpenClaw)       티스토리
─────────────────    ──────────────    ──────────────────────    ──────────────
글 작성 (.md)    →   git push      →   텔레그램 메시지 수신    →   자동 발행
이미지 첨부           이미지 포함        git pull + 스크립트 실행     이미지 포함
```

**이미지 방식:** GitHub Public 레포 raw URL → 별도 업로드 불필요

---

## 폴더 구조

```
~/tistory-bot/                         ← GitHub 레포 clone 위치 (Ubuntu)
├── tistory_playwright.py              # 핵심 배포 스크립트
├── tistory_login.py                   # 최초 1회 로그인 → 세션 저장
├── tistory_session.json               # 세션 쿠키 (자동 생성, git 제외)
├── .gitignore
├── posts/                             # 발행할 마크다운 파일들
│   └── 글제목.md
└── 00_첨부파일/                        # 옵시디언 이미지 첨부 폴더
    └── Pasted image xxxxxxxxxx.png
```

---

## 설치

### 1. Python 패키지

```bash
pip install playwright
playwright install chromium
playwright install-deps chromium   # Ubuntu 의존성
```

> `python` 명령어가 없을 경우: `sudo apt install python-is-python3`

### 2. CONFIG 설정

`tistory_playwright.py` 상단 CONFIG 수정:

```python
CONFIG = {
    "blog_name":     "your-blog-name",   # 티스토리 블로그 이름
    "github_user":   "your-github-id",   # GitHub 사용자명
    "github_repo":   "blog-posts",       # 레포 이름 (반드시 Public)
    "github_branch": "main",
}
```

### 3. 최초 로그인 (1회만)

```bash
python3 tistory_login.py
```

- 카카오 이메일/비밀번호 입력 (화면에 안 보임)
- 카카오 앱에서 2단계 인증 승인
- `tistory_session.json` 자동 저장

---

## 사용법

### 기본 발행 (최신 파일 자동 선택)

```bash
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py
```

### 파일 지정 발행

```bash
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py --file "posts/글제목.md"
```

### 임시저장 (발행 전 확인용)

```bash
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py --draft --file "posts/글제목.md"
```

### 옵션 정리

| 옵션 | 설명 |
|------|------|
| `--file 파일명.md` | 특정 파일 지정 (생략 시 최신 파일 자동 선택) |
| `--draft` | 임시저장 (발행 안 함, 테스트용) |
| `--no-pull` | git pull 생략 |

---

## 마크다운 작성 규칙

### 이미지 삽입

옵시디언에서 이미지를 붙여넣으면 자동으로 `00_첨부파일/` 폴더에 저장됩니다.

```markdown
![[Pasted image 20260220145957.png]]
```

→ GitHub raw URL로 자동 변환되어 티스토리에 표시됩니다.

### 지원 문법

| 마크다운 | 변환 결과 |
|---------|----------|
| `# 제목` | 글 제목으로 사용 |
| `## 소제목` | `<h2>` |
| `**볼드**` | **볼드** |
| `*이탤릭*` | *이탤릭* |
| `- 목록` | 불릿 리스트 |
| `> 인용` | 블록쿼트 |
| `![[이미지.png]]` | GitHub raw URL 이미지 |

---

## OpenClaw 스킬 등록

텔레그램에서 자연어로 발행 트리거하려면 스킬 등록이 필요합니다.

```bash
mkdir -p ~/.openclaw/skills/tistory
cat > ~/.openclaw/skills/tistory/SKILL.md << 'EOF'
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

파일명이 주어지면 --file 'posts/파일명.md' 옵션을 추가하세요.
EOF
```

텔레그램에서 `refresh skills` 후 사용 가능합니다.

---

## 일상 사용 흐름

```bash
# 1. 노트북에서 글 작성 후 push
git add posts/ 00_첨부파일/
git commit -m "새 글: 글제목"
git push

# 2. 텔레그램에서
# "티스토리 올려줘"
# → OpenClaw가 git pull + 스크립트 실행 → 자동 발행
```

---

## 트러블슈팅

### 세션 만료 시
```bash
python3 tistory_login.py
```

### UnicodeDecodeError
```bash
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py
```

### git pull 인증 오류
```bash
git remote set-url origin https://your-github-id:토큰@github.com/your-github-id/blog-posts.git
```

### 이미지가 안 보일 때
- GitHub 레포가 **Public** 인지 확인
- `00_첨부파일/` 폴더가 git에 포함됐는지 확인: `git ls-files | grep 첨부`

---

## 보안 체크리스트

- [ ] `tistory_session.json` → `.gitignore` 포함 확인
- [ ] GitHub 레포 **Public** (이미지 raw URL 접근용)
- [ ] Personal Access Token 코드/대화창에 노출 금지
- [ ] 노출된 토큰은 즉시 revoke 후 재발급
- [ ] 텔레그램 봇 토큰 타인 공유 금지
