"""
티스토리 로그인 세션 저장 스크립트 (최초 1회만 실행)
=====================================================
화면 없는 우분투 서버에서도 동작합니다 (headless 방식)
비밀번호는 터미널에서만 입력하고 어디에도 저장되지 않습니다

실행:
  python3 tistory_login.py
"""

import asyncio
import getpass
from pathlib import Path
from playwright.async_api import async_playwright

# 세션 파일 저장 경로 (스크립트와 같은 폴더)
SESSION_FILE = Path(__file__).parent / "tistory_session.json"

# ✏️ 블로그 이름만 채워주세요
BLOG_NAME = "fakehuman"


async def save_login_session(email: str, password: str):
    print("\n🔐 headless 브라우저로 카카오 로그인 중...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 티스토리 로그인 페이지
        await page.goto("https://www.tistory.com/auth/login")
        await page.wait_for_load_state("networkidle")

        # 카카오 로그인 버튼 클릭 (실제 셀렉터)
        await page.click("a.btn_login.link_kakao_id")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)

        # 카카오 이메일/비밀번호 입력
        await page.fill("input[name='loginId'], #loginId--1", email)
        await page.fill("input[name='password'], #password--2", password)
        await page.click("button[type='submit']")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 2단계 인증 대기 - URL 변경 감지 및 페이지 버튼 출력
        print("\n📱 카카오 앱에서 2단계 인증을 승인해주세요!")
        print("   승인 후 페이지에 버튼이 나타나면 번호를 입력해서 직접 클릭할 수 있습니다.\n")

        success = False
        last_printed_url = ""
        for i in range(24):   # 5초 간격 × 24 = 120초
            await page.wait_for_timeout(5000)
            current_url = page.url

            # URL 바뀔 때마다 현재 페이지 버튼 목록 출력
            if current_url != last_printed_url:
                print(f"\n🔗 현재 URL: {current_url[:80]}")
                last_printed_url = current_url

                # 페이지의 클릭 가능한 버튼/링크 목록 출력
                elements = await page.query_selector_all("button, a[href], input[type='submit']")
                clickable = []
                for el in elements:
                    text = (await el.inner_text()).strip()
                    if text and len(text) < 30:
                        clickable.append((text, el))

                if clickable:
                    print("   클릭 가능한 버튼 목록:")
                    for idx, (text, _) in enumerate(clickable):
                        print(f"   [{idx}] {text}")

                    # 터미널에서 번호 입력받아 클릭
                    try:
                        choice = input("\n   클릭할 버튼 번호 입력 (없으면 엔터): ").strip()
                        if choice.isdigit() and int(choice) < len(clickable):
                            await clickable[int(choice)][1].click()
                            await page.wait_for_load_state("networkidle")
                            await page.wait_for_timeout(2000)
                            print(f"   ✅ [{clickable[int(choice)][0]}] 클릭 완료")
                    except Exception:
                        pass

            # tistory.com 으로 이동됐으면 성공
            current_url = page.url
            if "tistory.com" in current_url and "kakao.com" not in current_url and "kauth" not in current_url:
                success = True
                break

        if not success:
            print("\n❌ 로그인 실패! 아래를 확인해주세요:")
            print("   - 카카오 앱에서 2단계 인증을 승인했는지 확인")
            print("   - 이메일/비밀번호가 맞는지 확인")
            await browser.close()
            return False

        print("✅ 로그인 성공!")

        # 블로그 관리 페이지로 이동해서 세션 확정
        await page.goto(f"https://{BLOG_NAME}.tistory.com/manage")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)

        # 세션 저장
        await context.storage_state(path=str(SESSION_FILE))
        print(f"💾 세션 저장 완료: {SESSION_FILE}")
        print("✅ 이제 tistory_playwright.py 를 비밀번호 없이 사용할 수 있습니다!")

        await browser.close()
        return True


if __name__ == "__main__":
    print("=" * 50)
    print("  티스토리 로그인 세션 저장")
    print("=" * 50)

    if "YOUR_" in BLOG_NAME:
        print("⚠️  BLOG_NAME 을 먼저 채워주세요!")
        exit(1)

    if SESSION_FILE.exists():
        print(f"\n⚠️  세션 파일이 이미 존재합니다: {SESSION_FILE}")
        ans = input("덮어쓸까요? (y/n): ").strip().lower()
        if ans != "y":
            print("취소됨")
            exit()

    print("\n카카오 계정 정보를 입력해주세요.")
    print("(입력 내용은 화면에 표시되지 않으며 어디에도 저장되지 않습니다)\n")

    email = input("카카오 이메일: ").strip()
    password = getpass.getpass("카카오 비밀번호: ")   # 입력시 화면에 안보임

    asyncio.run(save_login_session(email, password))
