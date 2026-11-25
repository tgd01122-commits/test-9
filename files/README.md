# 📊 초보 투자자를 위한 사업보고서 분석기

DART 사업보고서(PDF/엑셀)를 올리면 재무제표 탭 보기, 재무비율 계산, 산업 평균 비교(Positive/Negative)를 쉽게 보여주는 Streamlit 앱.

## 실행 (로컬)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## GitHub + Streamlit Community Cloud 배포
1. 이 폴더를 GitHub 저장소로 push
   ```bash
   git init && git add . && git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<아이디>/<저장소>.git
   git push -u origin main
   ```
2. https://share.streamlit.io 접속 → GitHub 로그인 → **New app**
3. Repository / Branch(`main`) / Main file path(`app.py`) 선택 → **Deploy**
이후 `git push` 할 때마다 앱이 자동 갱신됩니다.

## 파일 구조
- `app.py` : 화면(DART 링크, 업로드, 재무제표 탭, 비율별 비교와 해석)
- `parsers.py` : PDF/엑셀 파싱, 계정과목 추출
- `industry_data.py` : 산업 평균(예시값)과 비율 해석 문구 — 공식 통계로 교체 권장

## 한계
- 계정값 자동 추출은 휴리스틱이라 파일 형식에 따라 틀릴 수 있음 → 앱에서 직접 수정 가능
- 스캔(이미지) PDF는 텍스트 추출 불가
- 산업 평균은 시연용 근사치

## 코드에 쓰인 Streamlit 기능
- st.sidebar : 파일 업로드
- st.tabs : 재무제표 / 재무비율 비교
- st.columns, st.container : 화면 배치
- st.selectbox, st.file_uploader : 산업 선택, 파일 올리기
- @st.cache_data : 파일 읽은 결과 저장
