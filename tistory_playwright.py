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
    """마크다운에서 제목, 본문 HTML, 이미지 목록 추출"""
    content = Path(filepath).read_text(encoding="utf-8")
    md_dir = Path(filepath).parent  # md 파일 기준 디렉토리

    # 첫 H1을 제목으로
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else Path(filepath).stem

    # 옵시디언 이미지 링크 ![[파일명.png]] → placeholder로 치환
    image_list = []  # [(placeholder, 실제파일경로), ...]

    def replace_obsidian_image(m):
        raw = m.group(1)  # 예: "screenshot.png" 또는 "images/screenshot.png"
        # 파이프(|) 뒤 크기 옵션 제거: ![[file.png|400]] → file.png
        img_name = raw.split("|")[0].strip()

        # md 파일과 같은 폴더 또는 하위 폴더에서 파일 찾기
        repo_root = Path(__file__).parent  # tistory-bot 루트 (= 레포 최상위)
        candidates = [
            md_dir / img_name,                        # posts/파일명
            md_dir / "images" / img_name,             # posts/images/파일명
            md_dir / "assets" / img_name,             # posts/assets/파일명
            repo_root / "00_첨부파일" / img_name,     # 옵시디언 기본 첨부 폴더
            repo_root / img_name,                     # 레포 루트
        ]
        found_path = None
        for c in candidates:
            if c.exists():
                found_path = str(c.resolve())
                break

        if found_path:
            idx = len(image_list)
            placeholder = f"IMAGE_PLACEHOLDER_{idx}"
            image_list.append((placeholder, found_path, img_name))
            return placeholder
        else:
            print(f"  ⚠️  이미지 파일 없음: {img_name}")
            return ""  # 없으면 제거

    body = re.sub(r"!\[\[(.+?)\]\]", replace_obsidian_image, content)

    # 일반 마크다운 이미지 ![alt](path) 도 처리
    def replace_md_image(m):
        alt, src = m.group(1), m.group(2)
        if src.startswith("http"):
            # 외부 URL은 그대로 <img> 태그
            return f'<img src="{src}" alt="{alt}">'
        img_path = md_dir / src
        if img_path.exists():
            idx = len(image_list)
            placeholder = f"IMAGE_PLACEHOLDER_{idx}"
            image_list.append((placeholder, str(img_path.resolve()), alt))
            return placeholder
        return ""

    body = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_md_image, body)

    # 간단한 마크다운 → HTML
    body = md_to_html(body)

    return title, body, image_list


def inline_format(text: str) -> str:
    """볼드, 이탤릭, 링크 등 인라인 요소 변환 (모든 라인 유형에 공통 적용)"""
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

        # 이미지 placeholder 단독 라인 → 그대로 유지 (나중에 <img>로 교체됨)
        if re.match(r"^IMAGE_PLACEHOLDER_\d+$", stripped):
            if in_list: html.append("</ul>"); in_list = False
            html.append(stripped)

        elif line.startswith("### "):
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


async def upload_image_to_tistory(page, image_path: str) -> str:
    """
    티스토리 에디터에 이미지를 업로드하고,
    티스토리가 에디터에 삽입한 치환자(##_Image_##)가 포함된 HTML을 반환.

    전략:
      1. 업로드 전 TinyMCE 본문 스냅샷 저장
      2. 숨겨진 file input에 set_input_files() 로 파일 전달
      3. 업로드 완료까지 최대 10초 대기 (img 태그 또는 치환자 등장 감지)
      4. 업로드 후 TinyMCE 본문 다시 읽어 새로 추가된 치환자/img 조각 반환
    """
    print(f"  🖼️  이미지 업로드 중: {Path(image_path).name}")

    # 업로드 전 에디터 내용 스냅샷
    before_html = await page.evaluate("""
        () => {
            const ed = typeof tinymce !== 'undefined'
                ? (tinymce.activeEditor || tinymce.editors[0]) : null;
            return ed ? ed.getContent() : '';
        }
    """)

    # 티스토리 글쓰기 페이지의 숨겨진 파일 input 찾기
    # (툴바 이미지 버튼 클릭 없이 바로 set_input_files 가능)
    file_input = await page.query_selector(
        "input[type='file'][accept*='image'], "
        "input[type='file'][name='uploadImage'], "
        "input#imageUpload, "
        "input.image-upload"
    )

    if not file_input:
        # fallback: 모든 file input 중 첫 번째
        file_input = await page.query_selector("input[type='file']")

    if not file_input:
        print(f"  ❌ 파일 input을 찾지 못했습니다.")
        return None

    # 파일 전달 → 티스토리가 자동 업로드 후 에디터에 치환자 삽입
    await file_input.set_input_files(image_path)

    # 업로드 완료 감지: 에디터 내용이 바뀔 때까지 최대 10초 폴링
    after_html = before_html
    for _ in range(20):
        await page.wait_for_timeout(500)
        after_html = await page.evaluate("""
            () => {
                const ed = typeof tinymce !== 'undefined'
                    ? (tinymce.activeEditor || tinymce.editors[0]) : null;
                return ed ? ed.getContent() : '';
            }
        """)
        if after_html != before_html:
            break

    if after_html == before_html:
        print(f"  ⚠️  업로드 후 에디터 변화 없음 (업로드 실패 또는 지연)")
        return None

    # 새로 추가된 부분만 추출
    # before에 없던 img 태그 또는 치환자 조각 반환
    print(f"  ✅ 업로드 완료 (에디터에 이미지 삽입됨)")
    return after_html  # 전체 HTML 반환 → 호출부에서 before와 비교해 diff 사용


async def post_to_tistory(title: str, content: str, image_list: list = None, draft: bool = False):
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

        # ── TinyMCE iframe 내부 포함 전체 구조 디버그 ───────────────
        debug_info = await page.evaluate("""
            () => {
                const result = {};

                // 1. TinyMCE iframe 확인
                const iframe = document.querySelector('iframe#editor-tistory_ifr, iframe[id*="mce"], iframe[id*="tistory"]');
                result.iframeId = iframe ? iframe.id : 'none';

                // 2. TinyMCE 툴바 버튼 목록
                const btns = document.querySelectorAll('.mce-toolbar button, .tox-toolbar button, [class*="toolbar"] button');
                result.toolbarButtons = Array.from(btns).slice(0, 20).map(b => ({
                    title: b.title || b.getAttribute('aria-label') || '',
                    className: b.className.substring(0, 80)
                }));

                // 3. 이미지 관련 요소 (숨김 포함)
                const allInputs = document.querySelectorAll('input');
                result.allInputs = Array.from(allInputs).map(el => ({
                    type: el.type,
                    id: el.id,
                    name: el.name,
                    className: el.className.substring(0, 60),
                    accept: el.accept
                }));

                // 4. 이미지 업로드 관련 버튼/링크
                const imgBtns = document.querySelectorAll('[class*="image"], [id*="image"], [class*="photo"], [class*="upload"]');
                result.imageElements = Array.from(imgBtns).slice(0, 10).map(el => ({
                    tag: el.tagName,
                    id: el.id,
                    className: el.className.substring(0, 80),
                    text: el.innerText ? el.innerText.substring(0, 30) : ''
                }));

                return result;
            }
        """)
        print(f"\n🔍 TinyMCE iframe id: {debug_info['iframeId']}")
        print(f"\n🔍 툴바 버튼 목록:")
        for btn in debug_info['toolbarButtons']:
            print(f"  title={btn['title']} class={btn['className']}")
        print(f"\n🔍 모든 input 목록 ({len(debug_info['allInputs'])}개):")
        for inp in debug_info['allInputs']:
            print(f"  type={inp['type']} id={inp['id']} name={inp['name']} accept={inp['accept']}")
        print(f"\n🔍 이미지/업로드 관련 요소:")
        for el in debug_info['imageElements']:
            print(f"  {el['tag']} id={el['id']} class={el['className']} text={el['text']}")
        # ────────────────────────────────────────────────────────────

        # ── 이미지 업로드 처리 (치환자 방식) ────────────────────────
        if image_list:
            print(f"\n🖼️  이미지 {len(image_list)}개 업로드 시작...")
            placeholder_to_tistory = {}  # placeholder → 티스토리 치환자 HTML

            for placeholder, img_path, img_name in image_list:
                after_html = await upload_image_to_tistory(page, img_path)
                if after_html:
                    placeholder_to_tistory[placeholder] = after_html
                else:
                    placeholder_to_tistory[placeholder] = None
                    print(f"  ⚠️  {img_name} 업로드 실패 → 이미지 제거")

            # 업로드 후 에디터를 비워두고, content의 placeholder를
            # 티스토리가 삽입한 치환자 HTML 조각으로 교체
            success_count = 0
            for placeholder, tistory_html in placeholder_to_tistory.items():
                if tistory_html:
                    # 에디터 전체 HTML에서 before_html 이후 추가된 부분이
                    # 치환자 조각 → content의 placeholder 자리에 삽입
                    content = content.replace(placeholder, tistory_html)
                    success_count += 1
                else:
                    content = content.replace(placeholder, "")

            print(f"✅ 이미지 처리 완료 ({success_count}개 성공)")

            # 에디터를 다시 비워서 본문 전체를 깨끗하게 주입할 준비
            await page.evaluate("""
                () => {
                    const ed = typeof tinymce !== 'undefined'
                        ? (tinymce.activeEditor || tinymce.editors[0]) : null;
                    if (ed) ed.setContent('');
                }
            """)
            await page.wait_for_timeout(500)
        # ────────────────────────────────────────────────────────────

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
    title, body, image_list = parse_markdown(str(md_path))
    print(f"📝 제목: {title}")
    if image_list:
        print(f"🖼️  이미지 {len(image_list)}개 감지:")
        for placeholder, img_path, img_name in image_list:
            exists = "✅" if Path(img_path).exists() else "❌ 파일없음"
            print(f"   {exists} {img_name}")
    else:
        print(f"🖼️  이미지 없음")
    mode = "임시저장" if args.draft else "발행"
    print(f"🚀 모드: {mode}")

    confirm = input("\n진행할까요? (y/n): ").strip().lower()
    if confirm != "y":
        print("취소됨")
        return

    asyncio.run(post_to_tistory(title, body, image_list=image_list, draft=args.draft))


if __name__ == "__main__":
    main()
