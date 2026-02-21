import asyncio
import os
import argparse
import re
from playwright.async_api import async_playwright

# === 설정 ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "tistory_session.json")
BLOG_NAME = "fakehuman"
WRITE_URL = f"https://{BLOG_NAME}.tistory.com/manage/newpost/"

# === V1에서 가져온 마크다운 파서 ===
def inline_format(text: str) -> str:
    text = re.sub(r"`([^`]+)`", lambda m: f'<code style="background:#f0f0f0;padding:2px 5px;border-radius:3px;font-family:monospace;">{m.group(1)}</code>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text

def md_to_html(md: str) -> str:
    lines = md.split("\n")
    html = []
    in_ul = False
    in_ol = False
    
    for line in lines:
        stripped = line.strip()
        
        # 헤딩
        if line.startswith("### "):
            html.append(f"<h3>{inline_format(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            html.append(f"<h2>{inline_format(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            html.append(f"<h1>{inline_format(line[2:].strip())}</h1>")
        # 이미지
        elif line.startswith("!["):
            m = re.match(r'!\[(.*?)\]\((.*?)\)', line)
            if m:
                alt, url = m.groups()
                html.append(f'<figure><img src="{url}" alt="{alt}" style="max-width:100%;"><figcaption>{alt}</figcaption></figure>')
        # 리스트
        elif re.match(r"^[-*]\s", line):
            if not in_ul: html.append("<ul>"); in_ul = True
            html.append(f"<li>{inline_format(line[2:].strip())}</li>")
        # 일반 텍스트
        elif stripped:
            if in_ul: html.append("</ul>"); in_ul = False
            html.append(f"<p>{inline_format(stripped)}</p>")
        else:
            if in_ul: html.append("</ul>"); in_ul = False

    if in_ul: html.append("</ul>")
    return "\n".join(html)

async def post_to_tistory(file_path):
    print("=" * 50, flush=True)
    print("🚀 티스토리 자동 포스팅 V3 (TinyMCE Engine)", flush=True)
    print("=" * 50, flush=True)

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # 제목/본문 분리
    if lines and lines[0].startswith("# "):
        title = lines[0].replace("# ", "").strip()
        content_md = "".join(lines[1:])
    else:
        title = os.path.basename(file_path).replace(".md", "")
        content_md = "".join(lines)

    # HTML 변환
    html_content = md_to_html(content_md)
    print(f"📝 제목: {title}", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=SESSION_FILE)
        page = await context.new_page()

        try:
            await page.goto(WRITE_URL)
            print(f"➡️  글쓰기 페이지 접속: {page.url}", flush=True)

            # 제목 입력
            await page.wait_for_selector("#post-title-inp")
            await page.fill("#post-title-inp", title)
            print("✅ 제목 입력 완료", flush=True)

            await page.wait_for_timeout(2000)

            # TinyMCE에 HTML 직접 주입 (V1 방식)
            escaped = html_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            
            await page.evaluate(f"""
                if (typeof tinymce !== 'undefined') {{
                    const ed = tinymce.activeEditor || tinymce.editors[0];
                    if (ed) {{
                        ed.setContent(`{escaped}`);
                        ed.save();
                    }}
                }}
            """)
            print("✅ 본문 주입 완료 (TinyMCE)", flush=True)
            await page.wait_for_timeout(2000)

            # 완료 버튼 클릭
            print("➡️  완료 버튼 클릭", flush=True)
            try:
                await page.click("button.btn.btn-default", timeout=3000)
            except:
                await page.click("text=완료")
            
            await page.wait_for_timeout(1000)

            # 공개 설정 (V1 셀렉터 사용)
            print("➡️  공개 설정", flush=True)
            try:
                await page.click("label[for='open20']", force=True) # 공개
            except:
                print("⚠️ 공개 버튼 클릭 실패 (기본값 유지)", flush=True)

            # 최종 발행
            print("🚀 발행 시작...", flush=True)
            try:
                await page.click("#publish-btn", force=True) # V1 ID
            except:
                await page.click("button:has-text('발행')", force=True)

            # 완료 대기
            await page.wait_for_url("**/manage/posts**", timeout=15000)
            print("\n🎉 발행 완료!", flush=True)

        except Exception as e:
            print(f"\n❌ 오류: {e}", flush=True)
            await page.screenshot(path="error_v3.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    args = parser.parse_args()
    asyncio.run(post_to_tistory(args.file))
