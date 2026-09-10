# Streamlit 배포 따라 하기

어려운 말 없이 한 단계씩 진행합니다. 비밀번호나 API 키는 GitHub 파일에 쓰지 않습니다.

## 준비물

1. GitHub 계정
2. Streamlit Community Cloud 계정
3. 네이버 검색광고 API Key, Secret Key, Customer ID

## 1. GitHub에 빈 저장소 만들기

1. https://github.com/new 에 접속합니다.
2. Repository name에 `coupang-kw-recommend`를 입력합니다.
3. Public 또는 Private을 선택합니다.
4. Create repository를 누릅니다.

Private 저장소를 쓰려면 Streamlit이 해당 저장소를 볼 수 있도록 권한을 허용해야 합니다.

## 2. 이 폴더를 GitHub에 올리기

아래 명령에서 `내아이디`를 자신의 GitHub 아이디로 바꿉니다.

```bash
git add .
git commit -m "Build Coupang keyword recommender"
git remote add origin https://github.com/내아이디/coupang-kw-recommend.git
git push -u origin main
```

`.env`와 `.streamlit/secrets.toml`은 올리지 않습니다. `.gitignore`가 두 파일을 막고 있습니다.

## 3. Streamlit에 연결하기

1. https://share.streamlit.io 에 접속합니다.
2. GitHub 계정으로 로그인하고 연결을 허용합니다.
3. 오른쪽 위 Create app을 누릅니다.
4. `Yup, I have an app`을 선택합니다.
5. Repository에서 `coupang-kw-recommend`를 선택합니다.
6. Branch는 `main`을 선택합니다.
7. Main file path에는 `streamlit_app.py`를 입력합니다.

## 4. 비밀 열쇠 넣기

Deploy를 누르기 전에 Advanced settings를 엽니다. Secrets 칸에 아래 형식을 붙여넣고 따옴표 안에 실제 값을 입력합니다.

```toml
NAVER_AD_API_KEY = "실제 API Key"
NAVER_AD_SECRET_KEY = "실제 Secret Key"
NAVER_AD_CUSTOMER_ID = "실제 Customer ID"
```

이 값은 채팅, GitHub, 화면 캡처에 공개하지 않습니다.

## 5. 배포하기

1. Save를 누릅니다.
2. Deploy를 누릅니다.
3. 몇 분 기다리면 `https://...streamlit.app` 주소가 만들어집니다.
4. 상품명을 입력하고 먼저 `시드만 확인`을 켜서 테스트합니다.
5. 정상이라면 `시드만 확인`을 끄고 실제 추천을 실행합니다.

## 문제가 생겼을 때

- `ModuleNotFoundError`: GitHub 루트에 `requirements.txt`와 `streamlit_app.py`가 있는지 확인합니다.
- API 열쇠가 없다는 메시지: Streamlit 앱의 Settings → Secrets에서 세 값을 확인합니다.
- 추천이 0개: `recommend.yaml`의 카테고리 단어와 미보유 기능 필터를 확인합니다.
- 429 오류: 잠시 기다렸다가 다시 실행합니다. 프로그램은 해당 청크를 기록하고 나머지 청크를 계속 처리합니다.
