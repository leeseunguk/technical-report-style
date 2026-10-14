# 범용 교재형 보고서 스킬

주제와 분야에 관계없이 같은 스타일의 Word 문서를 작성한다.
기본 템플릿에 기존 연구 본문이나 그림은 들어 있지 않다.
특정 GSR/QTN 자료 없이 실행할 수 있다.

## 에이전트에게 요청하기

> technical-report-style 스킬로 이 자료를 쉽게 설명하는 Word 보고서를 작성해줘.
> 필요한 그림·표·수식을 넣고, 그림은 본문에서 설명하고 출처를 달아줘.
> PDF로 전체 페이지를 확인해서 같이 줘.

기존 문서에 붙이려면 원본 경로와 “후속 장으로 이어 써줘”를 덧붙인다.
원본은 보존하고 새 파일을 만든다.

“그림과 인포그래픽을 많이” 같은 요구는 문서별 필수 조건으로 기록한다.
집필 전에 절별 논문 그림·개념도·결과 그림 계획을 세우고 주요 개념의
시각화 누락을 확인한다. 인포그래픽 설계와 실제 이미지는 리드가
직접 열어 본문과 대조한다. 내용 확정 후에는 **im-not-ai 최종 윤문**과 보존 검사를
거친 원고를 최종 조판하고 모든 페이지를 다시 확인한다.

명시적 로드:

```bash
omo --skill "$HOME/.omo/agent/skills/technical-report-style"
```

## 직접 생성하기

Python 3.11 이상과 `python-docx`, `Pillow`, `pydantic>=2`, `typer`, `lxml`이
필요하다. 현재 환경에는 설치되어 있다. 진입점의 PEP 723 의존 목록을
지원하는 `uv run`도 사용할 수 있다.

```bash
S="$HOME/.omo/agent/skills/technical-report-style"
python3 "$S/scripts/build_report.py" \
  --manuscript "$S/examples/manuscript.json" \
  --ledger "$S/examples/source_ledger.json" \
  --output ./my-report.docx --mode new
```

`--ledger`는 선택이다. 생략해도 문서는 만들어진다. 주면 번호 수식, 그림, 표마다
장부 항목이 있어야 하고, 장부의 파일은 원고 JSON 위치에서 열려야 한다.
장부는 검사 입력이며 문서에 들어가지 않는다. 인용된 쪽 번호나 식 번호가
원문과 맞는지는 검사하지 않는다.

이어쓰기:

```bash
python3 "$S/scripts/build_report.py" \
  --source ./original.docx --manuscript ./continuation.json \
  --output ./continued.docx --mode append
```

출력과 감사 JSON이 이미 있으면 덮어쓰지 않고 실패한다.
`append`에는 원본을 반드시 지정한다. `new`는 동봉 템플릿이 기본이며,
`--source`로 다른 기준 문서를 지정할 수도 있다.

## 입력 구조

`blocks`에는 `h`(제목), `p`(본문), `eq`(편집 가능한 Word 수식),
`table`, `figure`를 순서대로 둔다. `assets`의 상대 경로는 원고 JSON
위치 기준이다. 그림이 없으면 `assets`를 생략할 수 있다.
외부 인용이 없으면 `references`도 생략할 수 있다.
표의 행 길이는 머리행과 같아야 한다.

학습 목표와 요점 정리 상자는 `p`에 `role: "callout-title"` 또는
`role: "callout-body"`를 지정한다. 원본 `Block Text` 스타일의 배경과
왼쪽 선을 계승하고 제목은 굵게 표시한다. 일반 문단은 `role`을 생략한다.

그림에는 `id`, `mention`, `asset`, `caption`, `source`를 넣고,
바로 앞 본문에서 `mention`으로 설명한다. 캡션에도 같은 표기와
출처 문자열을 넣는다. 식과 표에도 `source`가 필수다. 식의 `source`는
식 바로 다음 본문 문단(연속된 식은 그 묶음 다음 문단)에 그대로 들어간다.
표의 `source`는 바로 앞이나 뒤 문단에 들어간다. 출처 문자열은 참고문헌
`cite`, 원고 디렉터리에서 열리는 파일 경로, 또는 `이 문서`/`이 교재`/
`본 연구`/`this document` 중 하나를 포함해야 한다. 저자-연도 인용은
참고문헌 `cite`와 맞아야 한다. 실제 입력 예제는 [examples/manuscript.json](examples/manuscript.json)과
[examples/source_ledger.json](examples/source_ledger.json)을 본다.

새 교재형 보고서는 `citation_style`을 `author-year`로 두고, 각 참고문헌의
`cite`에 본문과 같은 저자-연도 구절을 넣는다. `[key]`를 만들지 않는다.
사용자가 번호 인용을 지정하면 `citation_style`을 `numbered`로 두고 본문
`[key]`와 항목을 대응시킨다. 필드를 생략하면 항목이 `[key]`로 시작하거나
본문에 `[key]`가 있을 때만 번호 규칙이고, 그렇지 않으면 저자-연도 규칙이다.
`samples[0]`처럼 식별자에 붙은 대괄호와 연속 인덱싱은 인용이 아니다.
실제 인용 앞에는 공백을 둔다. Windows 경로의 역슬래시는 본문에서 그대로
쓸 수 있다. `eq.lines`는 읽을 수 있는 식 입력이다. 내부 변환용 수식 표기는
독자에게 보이는 원문으로 출력하지 않고 네이티브 OMML로 변환한다.
수식 가까운 본문에 의미·기호·단위·물리적 이유·적용 조건을 설명한다.
식 번호나 기호 목록만으로 이 해설을 대신하지 않는다.
분수·근호·첨자·지수 등 구조가 필요한 식은 `lines`와 같은 길이의
`latex` 목록을 함께 준다. `lines`만 주는 단순 선형식은 수식 객체 안에서
그대로 표현되며, `/`, `^`, `sqrt`를 자동으로 구조 해석하는 기능은 아니다.

```json
{"type":"eq","lines":["(1)  y = a/b"],"latex":["y=\\frac{a}{b}"],"source":"이 교재의 규약이다"}
```

바로 다음 본문 문단에는 그 `source`와 `(1)`이 있어야 한다.

## 포함된 규칙과 검사

- [스킬 전체 지침](SKILL.md)
- [용지·글꼴·제목·표·수식·캡션 규격](references/style.md)
- [논문 그림 hybrid 위치 검출·원본 캡처·출처 장부·전 페이지 검증](references/workflow.md)
- [im-not-ai 최종 윤문과 의미·수치·인용 보존](references/polishing.md)
- [다시 쓰기 교훈: 읽히는 교재 문장을 위한 규칙과 측정값](references/writing-lessons.md)
- [실행 도구의 상세 계약과 한계](IMPLEMENTATION.md)

CLI는 서식·원본 보존·입력 누락을 검사한다. 논문 검색이나 hybrid를
자동 실행하는 도구는 아니다. **에이전트가 실제 hybrid를 실행하고
원본을 캡처하여 증거를 남기는 절차**가 스킬에 포함되어 있다.
PDF 렌더·시각 검수와 과학적 타당성도 CLI 성공과 별도다.
im-not-ai는 기본 마지막 집필 단계이며 원본 `humanize-korean` 스킬을
별도로 읽고 실행한다. 사용자가 진단·자동 윤문을 명시적으로 면제하면
그 지시와 유지하는 검사를 작업 계획에 기록한다. 과학·수식·렌더 검증은
그대로 수행한다. CLI 자체가 윤문하는 것은 아니며 다른 환경에서는 원본
스킬과 리소스 설치가 필요하다.

기본 문장 검사(집필 직후와 윤문 직후, 사용자 명시적 면제 시 생략):

```bash
python3 "$S/scripts/check_prose.py" ./continuation.json
```

잘못된 현재형 활용(빼는다, 쓰는다)과 중복 문단은 오류, 부정 종결 과다·반복 단서·
숫자만 다른 반복 문단은 경고다. 의미나 과학적 타당성은 검사하지 않는다.

검사 실행:

```bash
python3 "$S/scripts/check_harness.py"
```

새 문서, 의도한 그림 재사용, 이어쓰기 보존, 그림 없는 문서,
잘못된 입력·덮어쓰기 거부, 원본 없는 이어쓰기 거부, Windows 경로,
리터럴 인덱스, 수식 입력과 네이티브 출력, 저자-연도 인용과 누락 인용,
명시적 번호 인용, 원본 학습 상자 스타일 적용, 문장 검사기의 오류 검출,
수식 해설 누락, 출처가 본문에 없음, 알 수 없는 저자-연도, 없는 파일,
장부 항목 누락, 예제와 장부의 통과를 검사한다.
다른 주제에 과거 예제의 수치·결론·장 번호를 복사하지 않는다.
