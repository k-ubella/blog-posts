"""
티스토리 Playwright 자동 배포 스크립트 (세션 방식 - 비밀번호 불필요)
=====================================================================
OpenClaw 또는 직접 실행 모두 가능

준비:
  1. 최초 1회: python tistory_login.py  → 브라우저에서 직접 로그인 → 세션 저장
  2. 이후부터: python tistory_playwright.py  → 비밀번호 없이 자동 발행

설치:
  pip install playwright
  playwright install chromium

사용법:
  python tistory_playwright.py                          # 기본 파일 발행
  python tistory_playwright.py --file "내글.md"         # 파일 지정
  python tistory_playwright.py --draft                  # 임시저장 (발행 안함)
"""

import asyncio
import argparse
import re
import sys
import io
import subprocess
from pathlib import Path

# 터미널 인코딩 강제 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8")

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("❌ playwright 미설치. 아래 명령어로 설치해주세요:")
    print("   pip install playwright && playwright install chromium")
    exit(1)

# =============================================
# ✏️  블로그 이름만 채워주세요 (비밀번호 불필요!)
# =============================================
CONFIG = {
    "blog_name": "fakehuman",
}

# 세션 파일 경로 (tistory_login.py 가 저장한 파일)
SESSION_FILE = Path(__file__).parent / "tistory_session.json"

# 발행할 기본 마크다운 파일
DEFAULT_MD_FILE = "posts/260220 OpenClaw 사용기.md"
# =============================================


def parse_markdown(filepath: str):
    """마크다운에서 제목과 본문 HTML 추출"""
    content = Path(filepath).read_text(encoding="utf-8")

    # 첫 H1을 제목으로
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else Path(filepath).stem

    # 옵시디언 이미지 링크 제거
    body = re.sub(r"!\[\[.*?\]\]", "", content)

    # 간단한 마크다운 → HTML
    body = md_to_html(body)

    return title, body


def md_to_html(md: str) -> str:
    lines = md.split("\n")
    html = []
    in_list = False

    for line in lines:
        if line.startswith("### "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h3>{line[4:].strip()}</h3>")
        elif line.startswith("## "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h2>{line[3:].strip()}</h2>")
        elif line.startswith("# "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h1>{line[2:].strip()}</h1>")
        elif line.strip() in ("---", "***"):
            if in_list: html.append("</ul>"); in_list = False
            html.append("<hr>")
        elif line.startswith("> "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<blockquote><p>{line[2:].strip()}</p></blockquote>")
        elif re.match(r"^[-*]\s", line):
            if not in_list: html.append("<ul>"); in_list = True
            html.append(f"<li>{line[2:].strip()}</li>")
        elif line.strip() == "":
            if in_list: html.append("</ul>"); in_list = False
            html.append("")
        else:
            if in_list: html.append("</ul>"); in_list = False
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            line = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         line)
            line = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', line)
            line = re.sub(r"(?<![\"'(])(https?://[^\s<]+)", r'<a href="\1">\1</a>', line)
            if line.strip():
                html.append(f"<p>{line.strip()}</p>")

    if in_list:
        html.append("</ul>")

    return "\n".join(html)


async def post_to_tistory(title: str, content: str, draft: bool = False):
    blog = CONFIG["blog_name"]
    write_url = f"https://{blog}.tistory.com/manage/newpost/"

    async with async_playwright() as p:
        # 세션 파일로 로그인 상태 복원 (비밀번호 불필요)
        browser = await p.chromium.launch(headless=True)   # 백그라운드 실행
        context = await browser.new_context(storage_state=str(SESSION_FILE))
        page = await context.new_page()

        # 로그인 상태 확인
        print("🔐 세션으로 로그인 상태 확인 중...")
        await page.goto("https://www.tistory.com")
        await page.wait_for_load_state("networkidle")

        # 로그인 여부 체크
        is_logged_in = await page.query_selector("a.link_myinfo, .area_my, [class*='my_info']")
        if not is_logged_in:
            print("⚠️  세션이 만료되었습니다. tistory_login.py 를 다시 실행해주세요.")
            await browser.close()
            return

        print("✅ 세션 로그인 성공")

        # 글쓰기 페이지로 이동
        print("📝 글쓰기 페이지 이동 중...")
        await page.goto(write_url)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 제목 입력 (textarea#post-title-inp 확인됨)
        await page.fill("textarea#post-title-inp", title)
        print(f"📌 제목 입력: {title}")

        # TinyMCE 에디터 로딩 대기
        await page.wait_for_timeout(3000)
        escaped = content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

        # TinyMCE setContent + textarea 동기화 한번에 처리
        injected = await page.evaluate(f"""
            (() => {{
                if (typeof tinymce !== 'undefined') {{
                    const ed = tinymce.activeEditor || tinymce.editors[0];
                    if (ed) {{
                        ed.setContent(`{escaped}`);
                        ed.save();
                        ed.fire('change');
                        ed.fire('input');
                        return 'tinymce';
                    }}
                }}
                // fallback: textarea#editor-tistory 직접 입력
                const ta = document.querySelector('textarea#editor-tistory');
                if (ta) {{
                    ta.value = `{escaped}`;
                    ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    ta.dispatchEvent(new Event('input',  {{ bubbles: true }}));
                    return 'textarea';
                }}
                return 'not_found';
            }})()
        """)
        print(f"✍️ 본문 입력 완료 (방식: {injected})")
        await page.wait_for_timeout(2000)

        if draft:
            # 임시저장 버튼 클릭
            await page.click("a.action")
            await page.wait_for_timeout(3000)
            print("💾 임시저장 완료")
        else:
            # 완료 버튼 클릭 → 발행 팝업 열림 (button 태그 확인됨)
            await page.click("button.btn.btn-default")
            await page.wait_for_timeout(2000)
            print("📋 발행 팝업 열림")

            # 공개 라디오 버튼 클릭 (input#open20, value='20' 확인됨)
            await page.click("input#open20")
            await page.wait_for_timeout(500)
            print("🌐 공개 설정 완료")

            # 발행 버튼 클릭 (button#publish-btn 확인됨)
            await page.click("button#publish-btn")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)

            current_url = page.url
            print(f"\n🎉 발행 완료!")
            print(f"🔗 URL: {current_url}")

        await browser.close()


def git_pull():
    """GitHub에서 최신 파일 pull"""
    repo_dir = Path(__file__).parent
    git_dir = repo_dir / ".git"
    if not git_dir.exists():
        print("⚠️  git 레포가 아닙니다. git pull 생략.")
        return False

    print("📦 GitHub에서 최신 파일 받는 중...")
    result = subprocess.run(
        ["git", "pull"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"✅ git pull 완료: {result.stdout.strip()}")
        return True
    else:
        print(f"⚠️  git pull 실패: {result.stderr.strip()}")
        return False


def get_latest_md():
    """posts 폴더에서 가장 최근에 수정된 md 파일 반환"""
    posts_dir = Path(__file__).parent / "posts"
    if not posts_dir.exists():
        return None
    md_files = sorted(posts_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return md_files[0] if md_files else None


def main():
    parser = argparse.ArgumentParser(description="티스토리 자동 배포")
    parser.add_argument("--file",   default=None,  help="마크다운 파일 경로 (생략시 최신 파일 자동 선택)")
    parser.add_argument("--draft",  action="store_true", help="임시저장 (발행 안함)")
    parser.add_argument("--no-pull", action="store_true", help="git pull 생략")
    args = parser.parse_args()

    # 설정 확인
    if "YOUR_" in CONFIG["blog_name"]:
        print("⚠️  CONFIG의 blog_name 을 채워주세요! (예: myblog)")
        return

    # 세션 파일 확인
    if not SESSION_FILE.exists():
        print("⚠️  세션 파일이 없습니다. 먼저 아래를 실행해주세요:")
        print("   python3 tistory_login.py")
        return

    # git pull (--no-pull 옵션 없으면 항상 실행)
    if not args.no_pull:
        git_pull()

    # 파일 경로 결정
    if args.file:
        # 파일 직접 지정
        md_path = Path(__file__).parent / args.file
        if not md_path.exists():
            md_path = Path(args.file)
        if not md_path.exists():
            print(f"❌ 파일 없음: {args.file}")
            return
    else:
        # 최신 파일 자동 선택
        md_path = get_latest_md()
        if not md_path:
            print("❌ posts/ 폴더에 md 파일이 없습니다.")
            return
        print(f"📂 최신 파일 자동 선택: {md_path.name}")

    print(f"📄 파일: {md_path.name}")
    title, body = parse_markdown(str(md_path))
    print(f"📝 제목: {title}")
    mode = "임시저장" if args.draft else "발행"
    print(f"🚀 모드: {mode}")

    confirm = input("\n진행할까요? (y/n): ").strip().lower()
    if confirm != "y":
        print("취소됨")
        return

    asyncio.run(post_to_tistory(title, body, draft=args.draft))


if __name__ == "__main__":
    main()
