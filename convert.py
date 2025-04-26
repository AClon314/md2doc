#!/usr/bin/env python
# -*- coding: utf-8 -*-
__VERSION__ = 'v0.1.2025.04 from https://github.com/AClon314/md2doc'
import re
import os
import heapq
import argparse
import webbrowser
def Alt(t='图'): return ("\n" + t + r"\{\} ?(.*)\n", "\n" + t + "{chapter}-{i} {name}\n")
def CodeFigure(lang=r'mermaid|plantuml|chartjs'): return (r"<!--(.*?)-->\n```.*" + rf"({lang})" + r".*\n([\s\S]*?)\n```", """::: {{custom-style="Figure"}}\n```{1}\n{2}\n```\n""" + Alt('图')[1] + ":::")
def Match(key: str, text: str): return re.search(PATTERN[key][0], text)
def unescape(text: str): return re.sub(r'\\([^n])', r'\1', text)
def push(queue: list, key: str, match: re.Match | None): heapq.heappush(queue, (match.start(), key, match)) if match else None


PATTERN = {
    'photo': (r"""\n!\[(.*) ?(.*)\]\(([^ \t\r\n]+) ?['"]?(.*)['"]?\)\n""", """
::: {{custom-style="Figure"}}
![图{chapter}-{i} 	 {name}]({url} '图{i} {name} {hint}'){{ width=80% }}
:::
"""),
    'codeFig': CodeFigure(),
    '图': Alt('图'),
    'table': (r"<!--(.*?)-->(\n.*\n\| *[:-].*\n[\s\S]*?)\n\n", """\n
::: {{custom-style="Figure"}}
表{chapter}-{i} 	 {0}
{1}
:::
<br>\n\n"""),
    '表': Alt('表'),
}
RULES = {
    'photo': {
        'name': 0,
        'url': 2,
        'hint': 3,
    },
    'codeFig': {
        'name': 0,
    },
    '图': {
        'name': 0
    },
}
# print(unescape(str(PATTERN)))


def sub(filename: str):
    """
    替换脚注
    :param filename: 文件名
    :return: None
    """
    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()

    queue = []
    push(queue, 'photo', Match('photo', text))
    push(queue, 'codeFig', Match('codeFig', text))
    push(queue, '图', Match('图', text))
    text = _sub_priority(text, queue)

    queue = []
    push(queue, 'table', Match('table', text))
    push(queue, '表', Match('表', text))
    text = _sub_priority(text, queue)

    match = re.findall(r"\n# (.+)\n", text)
    for m in match:
        text = re.sub(f"\n# {m}\n", r"\n\\pagebreak\n# " + m + '\n', text)

    new_file = 'doc_' + os.path.splitext(filename)[0] + '.md'
    with open(new_file, 'w', encoding='utf-8') as f:
        f.write(text)
    return new_file


def _sub_priority(text, queue):
    idx = 1
    ch_old = 0
    while queue:
        _, key, match = heapq.heappop(queue)
        g = list(match.groups())
        ch = len(re.findall(r'\n# [一-龟\w]+\n', text[:match.start()]))
        if ch != ch_old:
            idx = 1
            ch_old = ch

        From, To = From_To(match, key, ch, idx, g)
        text = re.sub(From, To, text)
        idx += 1
        # print(f"☀️替换：{unescape(From)} -> {To}")

        next_match = Match(key, text)
        heapq.heappush(queue, (next_match.start(), key, next_match)) if next_match else None
    return text


def From_To(match: re.Match, key, chapter, idx, group: list[str]) -> tuple[str, str]:
    rule = RULES.get(key, {})
    kw = {k: group[v] for k, v in rule.items()}
    From, To = _From_To(match, key, chapter, idx, *group, **kw)
    return From, To


def _From_To(match: re.Match, key, chapter, idx, *args, **kwargs):
    From = re.escape(match.group())
    To = PATTERN[key][1].format(*args, i=idx, chapter=chapter, **kwargs)
    return From, To


def main():
    print(__VERSION__)
    args = argParse()

    if not args.raw:
        Input = sub(args.input)
    else:
        Input = args.input
    # return

    if not args.output:
        args.output = os.path.splitext(args.input)[0] + '.docx'

    if args.diy:
        args.output = "conf/diy_template.docx"
        cmd = f"pandoc -o {args.output} --print-default-data-file reference.docx"
        print("💾 需要另存为.docx一次，才能使用一些高级功能，如：主题👔")
    else:
        cmd = f"pandoc --defaults={args.yaml} --resource-path='{os.path.dirname(args.input)}' '{Input}' -o '{args.output}'"
    print(cmd)
    os.system(cmd)

    yn = input(f"📂 Open {args.output} [Y/n]: ")
    if yn.lower() in ["", "y"]:
        webbrowser.open(args.output)


def argParse():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description="""
Markdown.md to .docx/.pptx by pandoc & marpit
💡 Get started: https://st1020.com/write-thesis-with-markdown-part1/
💡 Set default table style: https://github.com/jgm/pandoc/issues/3275#issuecomment-369198726""")
    parser.add_argument("input", nargs="?", default="README.md",
                        help="input.md")
    parser.add_argument("output", nargs="?", help="output.docx")
    parser.add_argument("-r", "--raw", action="store_true", help=f"No post process, eg: `图{{}} name` → `图1-1 name` will be NOT applied")
    parser.add_argument("--yaml", default="conf/conf.yaml", metavar="conf/conf.yaml",
                        help="Default args in yaml config")
    parser.add_argument("--diy", action="store_true",
                        help="generate default pandoc diy_template.docx")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    main()
