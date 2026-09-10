# coupang-kw-recommend

네이버 검색광고 API의 연관 키워드를 쿠팡 광고용 후보로 정리하는 독립 Python 패키지입니다. 분석 코어를 import하지 않으며, 코어 산출 엑셀 또는 단순 CSV/TXT 시드 목록만 입력으로 받습니다.

## 설치

```bash
pip install .
coupang-kw-rec init
```

`init`은 현재 디렉터리에 `recommend.yaml`과 `.env.example`을 생성합니다. `.env.example`을 `.env`로 복사한 뒤 네이버 검색광고 API Manager에서 발급받은 값을 입력합니다.

## 시드 점검

API 호출 전에 선정되는 시드를 확인합니다.

```bash
coupang-kw-rec recommend --seeds seeds.txt --dry-run
coupang-kw-rec recommend --source output/키워드운영제안_YYYYMMDD.xlsx --dry-run
```

`--source`와 `--seeds`를 함께 사용할 수도 있습니다.

## 실제 추천 실행

먼저 `coupang-kw-rec init`으로 만든 `.env.example`을 `.env`로 복사하고 네이버 검색광고 API 값을 입력합니다. 인증정보는 채팅이나 GitHub에 올리지 않습니다.

```bash
coupang-kw-rec recommend --seeds seeds.txt --limit 500 --out output
```

캐시만 사용하려면 `--offline`을 붙입니다.

## Streamlit 웹 앱

```bash
streamlit run streamlit_app.py
```

브라우저에서 상품명 또는 핵심 키워드를 한 줄씩 입력할 수 있습니다. 코어 분석 엑셀, `contract.json`, 제외키워드 파일은 선택 입력입니다. 실행 후 엑셀 보고서와 세 종류 CSV를 내려받을 수 있습니다.

Streamlit Community Cloud 배포는 [DEPLOY_STREAMLIT.md](DEPLOY_STREAMLIT.md)를 순서대로 따라 하면 됩니다. 배포 엔트리 파일은 `streamlit_app.py`입니다.

## 비개발자용 빌드

- Windows: `build.bat`
- macOS/Linux: `./build.sh`

PyInstaller 설치 또는 빌드가 실패하면 원인을 출력하고 종료 코드 0으로 끝내 상위 파이프라인을 막지 않습니다.

## 공식 API 기준

- 서비스 URL: `https://api.searchad.naver.com`
- 키워드 도구: `GET /keywordstool`
- 서명 대상: `{timestamp}.{method}.{uri}`이며 쿼리 문자열은 uri에 포함하지 않습니다.

공식 문서: https://naver.github.io/searchad-apidoc/

## 결과 주의사항

네이버와 쿠팡은 검색 행동과 구매 의도가 다릅니다. 네이버 검색량과 경쟁도는 쿠팡의 절대 검색량·경쟁도를 뜻하지 않으며 상대적인 우선순위로만 사용합니다. 등록 전 쿠팡 검색결과에서 자사 상품 노출 여부를 확인해야 합니다.
