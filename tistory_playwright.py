"""
티스토리 Playwright 자동 배포 스크립트 (세션 방식 - 비밀번호 불필요)
=====================================================================
이미지: GitHub Public 레포 raw URL 방식 (업로드 불필요)

준비:
  1. 최초 1회: python tistory_login.py  → 브라우저에서 직접 로그인 → 세션 저장
  2. 이후부터: python tistory_playwright.py  → 비밀번호 없이 자동 발행

설치:
  pip install playwright
  playwright install chromium

사용법:
  python tistory_playwright.py                          # 최신 파일 자동 발행
  python tistory_playwright.py --file "내글.md"         # 파일 지정
  python tistory_playwright.py --draft                  # 임시저장 (발행 안함)
  python tistory_playwright.py --no-pull                # git pull 생략
"""

import asyncio
import argparse
import re
import sys
import io
import urllib.parse
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
# ✏️  설정값 채워주세요
# =============================================
CONFIG = {
    "blog_name":     "fakehuman",    # 티스토리 블로그 이름
    "github_user":   "k-ubella",     # GitHub 사용자명
    "github_repo":   "blog-posts",   # 레포 이름 (Public)
    "github_branch": "main",         # 브랜치
}
# =============================================

SESSION_FILE = Path(__file__).parent / "tistory_session.json"


def github_raw_url(img_name: str) -> str | None:
    """이미지 파일명 → GitHub raw URL 변환 (레포 내 경로 자동 탐색)"""
    repo_root = Path(__file__).parent
    user   = CONFIG["github_user"]
    repo   = CONFIG["github_repo"]
    branch = CONFIG["github_branch"]

    candidates = [
        repo_root / "00_첨부파일" / img_name,
        repo_root / "posts" / img_name,
        repo_root / "posts" / "images" / img_name,
        repo_root / img_name,
    ]
    for c in candidates:
        if c.exists():
            rel = c.resolve().relative_to(repo_root.resolve())
            encoded = "/".join(urllib.parse.quote(part) for part in rel.parts)
            return f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{encoded}"

    print(f"  ⚠️  이미지 파일 없음: {img_name}")
    return None


def inline_format(text: str) -> str:
    """볼드, 이탤릭, 링크 인라인 변환"""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"(?<![\"'(])(https?://[^\s<]+)", r'<a href="\1">\1</a>', text)
    return text


def md_to_html(md: str) -> str:
    lines = md.split("\n")
    html = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if line.startswith("### "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h3>{inline_format(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h2>{inline_format(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<h1>{inline_format(line[2:].strip())}</h1>")
        elif stripped in ("---", "***"):
            if in_list: html.append("</ul>"); in_list = False
            html.append("<hr>")
        elif line.startswith("> "):
            if in_list: html.append("</ul>"); in_list = False
            html.append(f"<blockquote><p>{inline_format(line[2:].strip())}</p></blockquote>")
        elif re.match(r"^[-*]\s", line):
            if not in_list: html.append("<ul>"); in_list = True
            html.append(f"<li>{inline_format(line[2:].strip())}</li>")
        elif stripped == "":
            if in_list: html.append("</ul>"); in_list = False
            html.append("")
        else:
            if in_list: html.append("</ul>"); in_list = False
            formatted = inline_format(stripped)
            if formatted:
                html.append(f"<p>{formatted}</p>")

    if in_list:
        html.append("</ul>")

    return "\n".join(html)


def parse_markdown(filepath: str):
    """마크다운 → 제목 + HTML (이미지는 GitHub raw URL로 변환)"""
    content = Path(filepath).read_text(encoding="utf-8")

    # 첫 H1을 제목으로
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else Path(filepath).stem

    # 옵시디언 이미지 ![[파일명.png]] → <img src="GitHub raw URL">
    def replace_obsidian_image(m):
        img_name = m.group(1).split("|")[0].strip()
        url = github_raw_url(img_name)
        if url:
            print(f"  🖼️  {img_name}")
            return f'<img src="{url}" alt="{img_name}" style="max-width:100%;">'
        return ""

    body = re.sub(r"!\[\[(.+?)\]\]", replace_obsidian_image, content)

    # 일반 마크다운 이미지 ![alt](path)
    def replace_md_image(m):
        alt, src = m.group(1), m.group(2)
        if src.startswith("http"):
            return f'<img src="{src}" alt="{alt}" style="max-width:100%;">'
        url = github_raw_url(Path(src).name)
        if url:
            return f'<img src="{url}" alt="{alt}" style="max-width:100%;">'
        return ""

    body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_md_image, body)

    body = md_to_html(body)
    return title, body


async def post_to_tistory(title: str, content: str, draft: bool = False):
    blog = CONFIG["blog_name"]
    write_url = f"https://{blog}.tistory.com/manage/newpost/"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(SESSION_FILE))
        page = await context.new_page()

        # 로그인 상태 확인
        print("🔐 세션으로 로그인 상태 확인 중...")
        await page.goto("https://www.tistory.com")
        await page.wait_for_load_state("networkidle")

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

        # 제목 입력
        await page.fill("textarea#post-title-inp", title)
        print(f"📌 제목 입력: {title}")

        # TinyMCE 에디터 로딩 대기
        await page.wait_for_timeout(3000)

        escaped = content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

        # TinyMCE에 본문 주입
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
        print(f"✍️  본문 입력 완료 (방식: {injected})")
        await page.wait_for_timeout(2000)

        if draft:
            await page.click("a.action")
            await page.wait_for_timeout(3000)
            print("💾 임시저장 완료")
        else:
            await page.click("button.btn.btn-default")
            await page.wait_for_timeout(2000)
            print("📋 발행 팝업 열림")

            await page.click("input#open20")
            await page.wait_for_timeout(500)
            print("🌐 공개 설정 완료")

            await page.click("button#publish-btn")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)

            print(f"\n🎉 발행 완료!")
            print(f"🔗 URL: {page.url}")

        await browser.close()


def git_pull():
    repo_dir = Path(__file__).parent
    if not (repo_dir / ".git").exists():
        print("⚠️  git 레포가 아닙니다. git pull 생략.")
        return
    print("📦 GitHub에서 최신 파일 받는 중...")
    result = subprocess.run(["git", "pull"], cwd=str(repo_dir), capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ git pull 완료: {result.stdout.strip()}")
    else:
        print(f"⚠️  git pull 실패: {result.stderr.strip()}")


def get_latest_md():
    posts_dir = Path(__file__).parent / "posts"
    if not posts_dir.exists():
        return None
    md_files = sorted(posts_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return md_files[0] if md_files else None


def main():
    parser = argparse.ArgumentParser(description="티스토리 자동 배포")
    parser.add_argument("--file",    default=None, help="마크다운 파일 경로")
    parser.add_argument("--draft",   action="store_true", help="임시저장 (발행 안함)")
    parser.add_argument("--no-pull", action="store_true", help="git pull 생략")
    args = parser.parse_args()

    if not SESSION_FILE.exists():
        print("⚠️  세션 파일이 없습니다. 먼저 아래를 실행해주세요:")
        print("   python3 tistory_login.py")
        return

    if not args.no_pull:
        git_pull()

    if args.file:
        md_path = Path(__file__).parent / args.file
        if not md_path.exists():
            md_path = Path(args.file)
        if not md_path.exists():
            print(f"❌ 파일 없음: {args.file}")
            return
    else:
        md_path = get_latest_md()
        if not md_path:
            print("❌ posts/ 폴더에 md 파일이 없습니다.")
            return
        print(f"📂 최신 파일 자동 선택: {md_path.name}")

    print(f"📄 파일: {md_path.name}")
    title, body = parse_markdown(str(md_path))
    print(f"📝 제목: {title}")
    print(f"🚀 모드: {'임시저장' if args.draft else '발행'}")

    confirm = input("\n진행할까요? (y/n): ").strip().lower()
    if confirm != "y":
        print("취소됨")
        return

    asyncio.run(post_to_tistory(title, body, draft=args.draft))


if __name__ == "__main__":
    main()
