"""
index.html 안의 `const DATA = {...};` 블록을 새 JSON으로 통째로 교체한다.
CSS/레이아웃/그 외 스크립트는 절대 건드리지 않는다.

사용법:
    python3 patch_data.py index.html /tmp/live_data.json
"""

from __future__ import annotations

import json
import sys


def main():
    if len(sys.argv) != 3:
        print("usage: patch_data.py <html_path> <data_json_path>", file=sys.stderr)
        sys.exit(1)

    html_path, data_path = sys.argv[1], sys.argv[2]

    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    with open(data_path, encoding="utf-8") as f:
        new_data_raw = f.read().strip()

    # 유효한 JSON인지 먼저 확인 (깨진 데이터로 페이지를 망가뜨리지 않기 위해)
    json.loads(new_data_raw)

    marker = "const DATA = "
    start = html.index(marker) + len(marker)
    # 마커 뒤 첫 '{' 부터 중괄호 짝을 맞춰 JSON 객체의 끝을 찾는다
    assert html[start] == "{", "DATA 블록이 객체 리터럴로 시작하지 않습니다"
    depth = 0
    i = start
    in_string = False
    escape = False
    while i < len(html):
        ch = html[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
        i += 1
    end = i

    old_data = html[start:end]
    new_html = html[:start] + new_data_raw + html[end:]

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"DATA 블록 교체 완료: {len(old_data)} chars -> {len(new_data_raw)} chars")


if __name__ == "__main__":
    main()
