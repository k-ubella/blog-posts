# OpenClaw × 티스토리 자동 배포 세팅 가이드 (GitHub 연동)

## 전체 흐름

```
노트북에서 md 파일 작성
    ↓
GitHub Private 레포에 push
    ↓
텔레그램 "티스토리 올려줘"
    ↓
OpenClaw → git pull → tistory_playwright.py 실행
    ↓
티스토리 자동 발행 ✅
```

---

## Step 1. GitHub Private 레포 생성 (노트북에서)

1. GitHub에서 Private 레포 생성 (예: `blog-posts`)
2. 노트북에서:

```bash
cd ~/tistory-bot
git init
git remote add origin https://github.com/사용자명/blog-posts.git
echo "tistory_session.json" >> .gitignore   # 세션 파일은 절대 올리지 않기
git add .
git commit -m "init"
git push -u origin main
```

---

## Step 2. 우분투에서 git clone

```bash
cd ~
rm -rf tistory-bot   # 기존 폴더 삭제
git clone https://github.com/사용자명/blog-posts.git tistory-bot
cd tistory-bot
```

> ⚠️ `tistory_session.json` 은 git에 올라가지 않으므로
> clone 후 `python3 tistory_login.py` 로 세션 재생성 필요

---

## Step 3. GitHub 인증 설정 (우분투에서 pull 자동화)

매번 비밀번호 입력 없이 pull 하려면 Personal Access Token 설정:

```bash
git config --global credential.helper store
git pull   # 최초 1회 토큰 입력 → 이후 자동
```

또는 SSH 키 방식:
```bash
ssh-keygen -t ed25519 -C "your_email@gmail.com"
cat ~/.ssh/id_ed25519.pub   # GitHub Settings → SSH Keys 에 등록
```

---

## Step 4. OpenClaw 스킬 등록

```bash
mkdir -p ~/.openclaw/skills
nano ~/.openclaw/skills/tistory.yaml
```

아래 내용 입력:

```yaml
name: tistory_post
description: GitHub에서 최신 마크다운 파일을 가져와 티스토리에 발행합니다
trigger:
  - "티스토리 올려줘"
  - "블로그 발행해줘"
  - "포스팅 해줘"
  - "최신 글 올려줘"
action:
  type: shell
  command: "cd /home/faker/tistory-bot && PYTHONIOENCODING=utf-8 python3 tistory_playwright.py --file 'posts/{file}'"
parameters:
  file:
    description: 발행할 마크다운 파일 이름 (생략시 최신 파일 자동 선택)
    default: ""
```

---

## Step 5. 일상적인 사용 흐름

### 노트북에서 글 작성 후 push:
```bash
cp "새글.md" ~/tistory-bot/posts/
cd ~/tistory-bot
git add posts/새글.md
git commit -m "새 글 추가"
git push
```

### 텔레그램에서 발행:
```
# 최신 글 자동 발행
티스토리 올려줘

# 특정 파일 발행
"새글.md" 티스토리 올려줘
```

---

## 사용 가능한 명령어 옵션

```bash
# 최신 파일 자동 선택 + git pull 후 발행
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py

# 특정 파일 발행
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py --file "posts/새글.md"

# 임시저장 (테스트용)
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py --draft

# git pull 없이 발행
PYTHONIOENCODING=utf-8 python3 tistory_playwright.py --no-pull
```
