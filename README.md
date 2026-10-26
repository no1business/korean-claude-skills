# 한국판 클로드 스킬 모음 (korean-claude-skills)

해외에서 뜨는 클로드(Claude) 스킬을 **한국어로 말해도 바로 켜지게** 고친 한국판입니다.
만든 곳: [방구석프로](https://bangpro.ai.kr) · 인스타그램 [@bangpro_ai](https://instagram.com/bangpro_ai)

설치 가이드(그림 포함): https://bangpro.ai.kr/guide/marketing-03

## 스킬 목록

| 순위 | 스킬 | 이렇게 말하면 켜져요 | 받기 |
|---|---|---|---|
| 1 | copywriting — 상세페이지·카피 (진단부터, 지어낸 숫자 금지) | "상세페이지 써줘" | [zip](zips/copywriting.zip) |
| 2 | campaign-plan — 캠페인 기획서·주차별 일정표 (앤트로픽 공식) | "신메뉴 출시 계획 짜줘" | [zip](zips/campaign-plan.zip) |
| 3 | diagram-design — 도식·흐름도·조직도 | "주문 흐름 도식 그려줘" | [zip](zips/diagram-design.zip) |
| 4 | humanizer — AI 티 나는 글 다듬기 | "AI 티 안 나게 고쳐줘" | [zip](zips/humanizer.zip) |
| 5 | naver-blog-expert / kakao-channel-expert / instagram-expert | "네이버 블로그 키우고 싶어" | [네이버](zips/naver-blog-expert.zip) · [카카오](zips/kakao-channel-expert.zip) · [인스타](zips/instagram-expert.zip) |

## 방구석프로 자체 제작

| 스킬 | 이렇게 말하면 켜져요 | 받기 |
|---|---|---|
| blog-photo-writer — 사진 10장 + 메모 2줄로 블로그 글 (사진 분류·배치·내 말투·제목·해시태그) | 사진 올리고 "블로그 글 써줘" | [zip](zips/blog-photo-writer.zip) · [가이드](https://bangpro.ai.kr/guide/marketing-04) |
| roast-room-ko — AI 자문단 7명 원탁 회의 한국판 (원본 nateherkai/roast-room, MIT). PC 클로드 코드용 | `/roast-room 고민` | [zip](zips/roast-room-ko.zip) · [가이드](https://bangpro.ai.kr/guide/research-03) |
| ai-sales-ko — AI 영업사원: 채용공고로 회사 찾기 → 회사별 제안 메일 → 네이버·지메일(무료)로 하루 상한 지켜 자동 발송 → 답장 분류·미팅 제안. PC 클로드 코드용 | "영업 메일 보내줘" | [zip](zips/ai-sales-ko.zip) · [가이드](https://bangpro.ai.kr/guide/marketing-05) |

## 설치 (무료 플랜 가능)

1. Claude **설정 → 기능**에서 **코드 실행 및 파일 생성**을 켭니다.
2. 위 표에서 zip을 받습니다. 압축은 풀지 않습니다.
3. Claude **맞춤 설정 → 스킬 → + → 스킬 만들기 → 스킬 업로드**에서 zip을 올립니다.
4. 새 대화에서 한국어로 말하면 됩니다.

Claude Code: `skills/` 폴더의 원하는 스킬 폴더를 `~/.claude/skills/`에 복사하세요.

## 원본과 라이선스

각 스킬 폴더의 LICENSE와 SKILL.md 상단에 원작자를 표기했습니다. 방구석프로는 한국어 설명(호출 문구)과 한국 상황 안내만 더했습니다.

- copywriting — [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) (MIT)
- campaign-plan — [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) (Apache 2.0, 설명·안내 문구 수정)
- diagram-design — [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) (MIT)
- humanizer — [blader/humanizer](https://github.com/blader/humanizer) (MIT)
- blog-photo-writer — 방구석프로 제작 (MIT)
- ai-sales-ko — 방구석프로 제작 (MIT). 흐름 참고 [ethanplusai/harvey](https://github.com/ethanplusai/harvey) (MIT)
- roast-room-ko — [nateherkai/roast-room](https://github.com/nateherkai/roast-room) (MIT, AI Automation Society) 한국어판. 한글 글꼴 Pretendard (SIL OFL)
- naver/kakao/instagram expert — [jnMetaCode/agency-agents-ko](https://github.com/jnMetaCode/agency-agents-ko) (원본 [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents), MIT, 스킬 형식으로 변환)
