"""
티스토리 자동 배포 스크립트
============================
사용 전 준비사항:
1. https://www.tistory.com/guide/api/manage/register 에서 앱 등록
2. 아래 설정값(CONFIG) 채우기
3. python tistory_deploy.py 실행
"""

import urllib.request
import urllib.parse
import json
import webbrowser
import http.server
import threading
import re
from pathlib import Path

# =============================================
# ✏️  여기만 채워주세요
# =============================================
CONFIG = {
    "client_id":     "YOUR_APP_ID",       # 티스토리 앱 ID
    "client_secret": "YOUR_SECRET_KEY",   # 티스토리 Secret Key
    "blog_name":     "YOUR_BLOG_NAME",    # 블로그 주소 앞부분 (예: myblog.tistory.com → myblog)
    "redirect_uri":  "http://localhost:8080/callback",
}

# 발행할 마크다운 파일 경로 (같은 폴더의 파일명)
MD_FILE = "260220 OpenClaw 사용기.md"
# =============================================


# --- OAuth 인증 ---

_auth_code = None

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write("✅ 인증 완료! 이 창을 닫고 터미널로 돌아오세요.".encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write("❌ 인증 코드를 받지 못했습니다.".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 서버 로그 숨기기


def get_access_token():
    """OAuth 인증을 통해 Access Token 발급"""
    auth_url = (
        "https://www.tistory.com/oauth/authorize?"
        + urllib.parse.urlencode({
            "client_id":     CONFIG["client_id"],
            "redirect_uri":  CONFIG["redirect_uri"],
            "response_type": "code",
        })
    )

    print("\n🔐 브라우저에서 티스토리 로그인 후 앱 권한을 허용해주세요...")
    webbrowser.open(auth_url)

    # 로컬 콜백 서버 실행
    server = http.server.HTTPServer(("localhost", 8080), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    thread.join(timeout=120)
    server.server_close()

    if not _auth_code:
        raise Exception("❌ 인증 코드를 받지 못했습니다. 다시 시도해주세요.")

    # Access Token 요청
    token_url = "https://www.tistory.com/oauth/access_token"
    data = urllib.parse.urlencode({
        "client_id":     CONFIG["client_id"],
        "client_secret": CONFIG["client_secret"],
        "redirect_uri":  CONFIG["redirect_uri"],
        "code":          _auth_code,
        "grant_type":    "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request(token_url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = urllib.parse.parse_qs(resp.read().decode("utf-8"))
        token = result.get("access_token", [None])[0]

    if not token:
        raise Exception("❌ Access Token 발급 실패")

    print(f"✅ Access Token 발급 완료")
    return token


# --- 마크다운 파싱 ---

def parse_markdown(filepath: str):
    """마크다운 파일에서 제목과 본문을 추출"""
    content = Path(filepath).read_text(encoding="utf-8")

    # 첫 번째 H1을 제목으로 사용
    title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else Path(filepath).stem

    # 이미지 링크([[...]]) 제거 (티스토리 업로드 전 처리)
    body = re.sub(r"!\[\[.*?\]\]", "[이미지]", content)

    # 마크다운 → HTML 간단 변환
    body = md_to_html(body)

    return title, body


def md_to_html(md: str) -> str:
    """간단한 마크다운 → HTML 변환"""
    lines = md.split("\n")
    html_lines = []
    in_list = False

    for line in lines:
        # 제목
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:].strip()}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:].strip()}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{line[2:].strip()}</h1>")
        # 구분선
        elif line.strip() in ("---", "***", "___"):
            html_lines.append("<hr>")
        # 인용
        elif line.startswith("> "):
            html_lines.append(f"<blockquote>{line[2:].strip()}</blockquote>")
        # 리스트
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{line[2:].strip()}</li>")
        # 빈 줄
        elif line.strip() == "":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("")
        # 일반 텍스트
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            # 볼드/이탤릭 처리
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            line = re.sub(r"\*(.+?)\*", r"<em>\1</em>", line)
            # 링크 처리
            line = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', line)
            # URL 자동 링크
            line = re.sub(r"(?<![\"'])(https?://\S+)", r'<a href="\1">\1</a>', line)
            html_lines.append(f"<p>{line.strip()}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


# --- 티스토리 API 글 발행 ---

def post_to_tistory(access_token: str, title: str, content: str):
    """티스토리에 글 발행"""
    api_url = "https://www.tistory.com/apis/post/write"

    data = urllib.parse.urlencode({
        "access_token": access_token,
        "output":       "json",
        "blogName":     CONFIG["blog_name"],
        "title":        title,
        "content":      content,
        "visibility":   "3",   # 0: 비공개, 3: 발행
        "acceptComment": "1",
    }).encode("utf-8")

    req = urllib.request.Request(api_url, data=data, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    if result.get("tistory", {}).get("status") == "200":
        post_url = result["tistory"].get("url", "")
        print(f"\n🎉 발행 완료!")
        print(f"📝 제목: {title}")
        print(f"🔗 URL: {post_url}")
        return post_url
    else:
        raise Exception(f"❌ 발행 실패: {result}")


# --- 메인 실행 ---

def main():
    print("=" * 50)
    print("  티스토리 자동 배포 스크립트")
    print("=" * 50)

    # 설정 확인
    if "YOUR_" in CONFIG["client_id"]:
        print("\n⚠️  CONFIG 설정을 먼저 채워주세요!")
        print("   client_id, client_secret, blog_name 을 입력해야 합니다.")
        print("   앱 등록: https://www.tistory.com/guide/api/manage/register")
        return

    md_path = Path(__file__).parent / MD_FILE
    if not md_path.exists():
        print(f"\n❌ 파일을 찾을 수 없습니다: {MD_FILE}")
        return

    print(f"\n📄 파일: {MD_FILE}")
    title, body = parse_markdown(str(md_path))
    print(f"📝 제목: {title}")
    print(f"📏 본문 길이: {len(body)} 글자")

    confirm = input("\n위 내용으로 티스토리에 발행할까요? (y/n): ").strip().lower()
    if confirm != "y":
        print("취소되었습니다.")
        return

    try:
        token = get_access_token()
        post_to_tistory(token, title, body)
    except Exception as e:
        print(f"\n{e}")


if __name__ == "__main__":
    main()
