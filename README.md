# MediReg — 의료기기 규제 모니터링 시스템

식약처(MFDS), FDA, EU MDR, PMDA 등 규제기관 사이트를 **매주 자동 크롤링**하여 변경된 가이던스·고시·법령을 팀과 공유하는 시스템입니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| 자동 크롤링 | GitHub Actions로 매주 월요일 오전 9시(KST) 자동 실행 |
| 변경 감지 | 이전 스냅샷과 비교 → 신규 항목 자동 추출 |
| 규정 데이터베이스 | 식약처/FDA/EU MDR/PMDA/ISO/IEC/IMDRF 33종 수록 |
| 인허가 캘린더 | EU IVDR 전환기한, FDA QMSR 등 마감일 추적 |
| 라이브 대시보드 | GitHub Pages에서 팀 전체 접근 가능 |

## 구조

```
medireg/
├── .github/workflows/
│   ├── crawl.yml          # 매주 크롤링 (월요일 00:00 UTC)
│   └── pages.yml          # GitHub Pages 자동 배포
├── crawler/
│   ├── mfds.py            # 식약처 크롤러
│   ├── fda.py             # FDA RSS 크롤러
│   ├── eumdr.py           # EU MDR/MDCG 크롤러
│   ├── pmda.py            # PMDA 크롤러
│   ├── run_all.py         # 전체 실행 + diff 감지
│   └── requirements.txt
├── data/
│   ├── crawled.json       # 최신 크롤링 결과
│   ├── updates.json       # 변경 이력 (자동 누적)
│   ├── meta.json          # 마지막 크롤링 시각 등
│   └── snapshots/         # 날짜별 스냅샷 (gitignore)
└── dashboard/
    └── index.html         # 대시보드 (GitHub Pages 배포)
```

## 시작하기

### 1. GitHub 레포 생성 및 설정

```bash
git init
git add .
git commit -m "initial commit"
# GitHub에서 새 레포 생성 후:
git remote add origin https://github.com/<org>/medireg.git
git push -u origin main
```

### 2. GitHub Pages 활성화

레포 → **Settings → Pages → Source: GitHub Actions** 선택

### 3. 크롤링 수동 실행 (첫 데이터 수집)

레포 → **Actions → MediReg 규제 모니터링 크롤링 → Run workflow**

이후 매주 월요일 자동 실행됩니다.

### 4. 대시보드 접근

```
https://<org>.github.io/medireg/dashboard/
```

## 로컬 크롤링 실행

```bash
cd crawler
pip install -r requirements.txt
python run_all.py
```

## 크롤링 대상

| 기관 | 수집 항목 |
|------|-----------|
| 식약처 (MFDS) | 공지사항, 가이던스, 법령/고시 |
| FDA | 의료기기 가이던스 RSS, 리콜 RSS |
| EU (EC Health) | MDCG 가이던스, MDR 뉴스 |
| PMDA | 의료기기 통지/가이던스 |

## 기여

팀원 누구나 PR로 크롤러 개선 또는 규정 데이터 추가 가능합니다.
