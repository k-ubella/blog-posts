import asyncio
import os
from playwright.async_api import async_playwright
import getpass

# === 설정 ===
SESSION_FILE = "tistory_session.json"
TISTORY_LOGIN_URL = "https://fakehuman.tistory.com/manage"

async def run():
    print("=" * 50)
    print("🚀 티스토리(카카오) 로그인 세션 발급기 V2")
    print("=" * 50)

    # 1. 사용자 입력 받기
    user_id = input("카카오 계정 이메일(ID): ").strip()
    if not user_id:
        print("❌ 아이디가 입력되지 않았습니다.")
        return
    
    user_pw = getpass.getpass("카카오 계정 비밀번호: ").strip()
    if not user_pw:
        print("❌ 비밀번호가 입력되지 않았습니다.")
        return

    print("\n🌐 브라우저를 실행하고 접속 중입니다... (잠시만 기다려주세요)")

    async with async_playwright() as p:
        # 브라우저 실행 (헤드리스 모드)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # 2. 티스토리 접속 및 카카오 로그인 버튼 클릭
            await page.goto(TISTORY_LOGIN_URL)
            print("➡️  티스토리 로그인 페이지 접속 완료")
            
            # 카카오 계정으로 로그인 버튼 찾기 (선택자 유연하게 대응)
            kakao_btn = page.locator("a.btn_login.link_kakao_id") # 구형
            if not await kakao_btn.is_visible():
                kakao_btn = page.locator(".txt_kakao") # 신형 텍스트 등
            
            # 버튼이 안 보이면 바로 카카오 로그인 페이지로 리다이렉트 되었을 수 있음
            if "accounts.kakao.com" not in page.url:
                await kakao_btn.click()
                await page.wait_for_url("**/accounts.kakao.com/**", timeout=10000)
            
            print("➡️  카카오 로그인 화면 진입")

            # 3. 아이디/비번 입력
            await page.fill("#loginId--1", user_id)
            await page.fill("#password--2", user_pw)
            print("🔑 계정 정보 입력 완료")

            # 로그인 버튼 클릭
            await page.click("button.btn_g.highlight.submit")
            
            # 4. 로그인 결과 대기 (2차 인증 or 성공)
            print("⏳ 로그인 처리 중...")
            
            # 2~3초 대기 후 URL 확인
            await page.wait_for_timeout(3000)
            
            # 2차 인증 페이지 감지 (URL에 verify가 있거나, 특정 텍스트가 보이면)
            # 대기 시간을 좀 더 넉넉히 줌
            await page.wait_for_timeout(5000)
            
            if "risk/verify" in page.url or "two-step" in page.url or await page.locator("text=이중잠금").is_visible():
                print("\n" + "!"*50)
                print("📱 [2차 인증 필요] 카카오톡으로 발송된 인증을 확인해주세요!")
                print("   인증을 완료하신 후, 이곳 터미널에서 [Enter] 키를 눌러주세요.")
                print("!"*50 + "\n")
                input(">> 인증 완료 후 엔터 입력: ")
                
                # 인증 후 대기
                await page.wait_for_timeout(5000)

            # 티스토리 관리자 페이지 진입 확인 (중간에 버튼이 있으면 클릭 시도)
            try:
                print("⏳ 관리자 페이지 진입 대기 중... (중간 화면이 뜨면 처리를 시도합니다)")
                
                # 60초 동안 반복 체크
                for i in range(12): # 5초 * 12번 = 60초
                    # 멈춰있는 화면의 텍스트 확인
                    body_text = await page.inner_text("body")

                    # 성공 조건: 사이드바가 보이거나, '블로그 관리센터' 텍스트가 있거나, URL이 manage로 끝날 때
                    if await page.locator(".sidebar_menu").is_visible() or "블로그 관리센터" in body_text or "/manage" in page.url:
                        print("✅ 관리자 페이지 접속 성공! (인증 완료)")
                        break
                    
                    # '계속하기'나 '확인' 버튼이 보이면 클릭
                    
                    # '계속하기'나 '확인' 버튼이 보이면 클릭
                    if "로그인 상태 유지" in body_text or "이 브라우저에서" in body_text:
                        print("👉 '로그인 상태 유지' 화면 감지! 버튼 클릭 시도...")
                        # 1. 'user_id' (이메일) 텍스트가 있으면 클릭 (계정 선택 화면일 경우)
                        try:
                            if user_id in body_text:
                                print(f"👉 계정 선택 화면: {user_id} 클릭")
                                await page.click(f"text={user_id}")
                                await page.wait_for_timeout(2000)
                        except:
                            pass

                        # 2. 일반적인 버튼 클릭
                        try:
                            # 카카오 노란 버튼 (.btn_g) 또는 submit
                            if await page.locator("button[type='submit']").is_visible():
                                await page.click("button[type='submit']")
                            elif await page.locator(".btn_confirm").is_visible():
                                await page.click(".btn_confirm")
                        except:
                            pass

                    # '계속하기' 버튼이 보이면 클릭 (이게 핵심!)
                    if "계속하기" in body_text:
                        print("👉 '계속하기' 버튼 감지! 클릭 시도...")
                        try:
                            await page.click("text=계속하기")
                            await page.wait_for_timeout(2000)
                        except:
                            pass
                            
                    if "동의" in body_text or "Accept" in body_text:
                         try:
                            await page.click("button[type='submit']", timeout=2000)
                         except:
                            pass

                    await page.wait_for_timeout(5000)
                            
                    if "동의" in body_text or "Accept" in body_text:
                         try:
                            await page.click("button[type='submit']", timeout=2000)
                         except:
                            pass

                    await page.wait_for_timeout(5000)
                else:
                    raise Exception("타임아웃")

            except Exception as e:
                print(f"❌ 로그인 실패. 현재 URL: {page.url}")
                # 화면에 뭐가 떴는지 텍스트로 덤프
                text = await page.inner_text("body")
                print(f"\n📄 [화면 내용]\n{text[:500]}\n...")
                return

            # 5. 세션(쿠키) 저장
            await context.storage_state(path=SESSION_FILE)
            print(f"\n💾 세션 파일이 저장되었습니다: {os.path.abspath(SESSION_FILE)}")
            print("이제 이 파일을 이용해 자동 포스팅을 할 수 있습니다.")

        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            await page.screenshot(path="error_screenshot.png")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
