# 🕵️‍♀️ Darkweb Leak Monitor (Semi-project)

본 프로젝트는 텔레그램 기반 위협 인텔리전스 채널에서  
**유출·랜섬웨어·사이버 공격 관련 메시지를 자동 수집하고**,  
이를 **표준화된 데이터 구조(LeakRecord)**로 변환하여  
OSINT(Open Source Intelligence) 분석에 바로 활용 가능한 형태로 저장하는  
**위협 인텔리전스 파이프라인 PoC(Proof of Concept)**이다.

---

## 🎯 Project Objectives
- 텔레그램 기반 위협 인텔리전스 데이터 수집 자동화
- 채널별로 상이한 메시지 포맷을 공통 스키마(LeakRecord)로 통합
- OSINT 분석을 위한 검색·참조용 데이터(OSINT seeds) 생성
- 최근 유출 정보를 요약한 CSV / JSON 산출물 제공

---

## 🔄 Pipeline Overview
본 시스템은 다음과 같은 흐름으로 동작한다.

1. Telethon을 이용해 텔레그램 채널 메시지를 수집한다.
2. 채널별 파서를 통해 raw 메시지를 LeakRecord 구조로 변환한다.
3. URL, 도메인, 키워드 등 OSINT 분석용 seed 정보를 생성한다.
4. 최근 메시지를 집계하여 `leak_summary.csv` 및 `leak_summary.json`으로 저장한다.
5. 생성된 산출물은 OSINT 분석 및 후속 조사에 활용된다.

---

## 🧱 LeakRecord Schema
모든 데이터는 단일 표준 스키마인 **LeakRecord**로 통합된다.

- LeakRecord 필드 정의 및 팀 규격은 아래 문서에 고정되어 있다.  
  👉 `docs/leakrecord_spec.md`

이를 통해 채널별 데이터 편차를 최소화하고,  
후속 분석 및 확장 작업에서 일관성을 유지한다.

---

## 📡 Supported Telegram Channels
본 프로젝트에서는 다음 텔레그램 채널을 대상으로 파서를 구현하였다.

- `@RansomFeedNews`
- `@venarix`
- `@ctifeeds`
- `@hackmanac_cybernews`

---

## 🧭 Channel Roles & Characteristics
각 채널은 동일한 기준으로 평가되었으며,  
특성에 따라 다음과 같은 역할로 구분하여 활용한다.

| Channel | Role | Strengths | Limitations |
|------|------|-----------|-------------|
| RansomFeedNews | Main leak alert | URLs, target, actor, date | Domain extraction incomplete |
| Venarix | OSINT seed channel | Clear target & actor | No URLs |
| CTIFeeds | CTI / news reference | URLs & domains | No actor attribution |
| Hackmanac Cybernews | Summary intelligence | Target & actor | No URLs |

> 모든 채널은 실패가 아니라,  
> **서로 다른 정보 특성을 가진 위협 인텔리전스 소스로 분류**된다.

---

## 📤 Outputs
시스템 실행 결과는 아래 경로에 자동 저장된다.

- `data/leak_summary.csv`
- `data/leak_summary.json`

해당 파일은 OSINT 팀이 즉시 분석에 활용할 수 있는  
**최종 산출물**이다.

---

## 📁 Project Structure
Semi-project/
├── app/
│ ├── main_demo_manual.py
│ ├── main_demo_telegram.py
│ ├── parser.py
│ ├── storage.py
│ ├── notifier.py
│ ├── models.py
│ └── telegram_*.py
├── data/
│ ├── leak_summary.csv
│ └── leak_summary.json
├── docs/
│ └── leakrecord_spec.md
├── scripts/
│ └── qa_parser_coverage.py
├── README.md
└── .gitignore

---

## ▶ How to Run

```bash
# 샘플 데이터 기반 실행
python3 -m app.main_demo_manual

# 텔레그램 메시지 기반 실행
python3 -m app.main_demo_telegram
