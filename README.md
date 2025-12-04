# Semi-project
# 🕵️‍♀️ Darkweb Leak Monitor (Semi-project)

다크웹/텔레그램에서 유출 정보를 수집했다고 가정하고,  
메시지를 파싱 → 구조화(LeakRecord) → CSV/JSON 저장 → 알림 출력까지  
한 번에 실행되는 간단한 위협 인텔리전스 파이프라인입니다.

---

## 📁 프로젝트 구조

Semi-project/
├── app/
│ ├── main_demo.py # 샘플 데이터 기반 실행
│ ├── main_from_telegram.py # 텔레그램 메시지 기반 실행
│ ├── parser.py # 메시지 → LeakRecord 파서
│ ├── storage.py # CSV/JSON 저장
│ ├── notifier.py # 알림 출력
│ ├── models.py # LeakRecord 데이터 모델
│ └── init.py
├── data/
│ ├── leak_summary.csv
│ └── leak_summary.json
├── screenshots/
├── env/ # (선택) 가상환경
├── README.md
└── .gitignore

---

## 🛠 설치 방법

### 1) 프로젝트 클론

```bash
git clone https://github.com/seoh3e/Semi-project.git
cd Semi-project

2) (선택) 가상환경 생성
python3 -m venv env

3) 가상환경 활성화 (macOS)
source env/bin/activate

4) 패키지 설치
현재는 표준 라이브러리만 사용하므로 별도 패키지 설치는 필요 없습니다.
추후 필요 시 requirements.txt를 추가할 예정입니다.

▶ 실행 방법
📌 1. 샘플 다크웹 데이터 실행
python3 -m app.main_demo

📌 2. 텔레그램 메시지 파싱 실행
python3 -m app.main_from_telegram

💾 결과 저장 위치

파일은 아래에 자동 저장됩니다:
data/leak_summary.csv
data/leak_summary.json

📝 향후 개발 예정

중복 저장 방지(duplicate check)

실제 텔레그램 Bot API 연동

스크린샷 자동 수집/저장 기능

간단한 웹 대시보드