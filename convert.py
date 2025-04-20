#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import os
import argparse
import webbrowser
PATTERN = {
    'footnote': (r'\[\^(.+?)\]', '[^{}]'),
    'photo': (r"""\n!\[(.*) ?(.*)\]\(([^ \t\r\n]+) ?['"]?(.*)['"]?\)\n""", """\n
::: {{custom-style="Figure"}}
![图{i} 	 {name}]({url} '图{i} {name} {hint}'){{ width=80% }}
:::\n
"""),
}
def Match(key: str, text: str): return re.search(PATTERN[key][0], text)


def sub(filename: str):
    """
    替换脚注
    :param filename: 文件名
    :return: None
    """
    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()

    idx = 1
    match = re.findall(PATTERN['footnote'][0], text)
    for m in match:
        From = re.escape(PATTERN['footnote'][1].format(m))
        To = PATTERN['footnote'][1].format(idx)
        # print(f"替换脚注：{From} -> {To}")
        text = re.sub(From, To, text)
        idx += 1

    idx = 1
    match = Match('photo', text)
    while match:
        g = list(match.groups())
        From = re.escape(match.group())
        To = PATTERN['photo'][1].format(name=g[0], url=g[2], hint=g[3], i=idx)
        print(f"替换图片 {g}：{match.group()} -> {To}", end='')
        text = re.sub(From, To, text)
        match = Match('photo', text)
        idx += 1

    new_file = 'doc_' + os.path.splitext(filename)[0] + '.md'
    with open(new_file, 'w', encoding='utf-8') as f:
        f.write(text)
    return new_file


def main():
    parser = argparse.ArgumentParser(description="Convert markdown to docx")
    parser.add_argument("input", nargs="?", default="README.md",
                        help="input.md")
    parser.add_argument("output", nargs="?", help="output.docx")
    parser.add_argument("--defaults", default="conf/conf.yaml",
                        help="https://st1020.com/write-thesis-with-markdown-part1/")
    parser.add_argument("--diy", action="store_true",
                        help="pandoc -o diy_template.docx --print-default-data-file reference.docx")
    args = parser.parse_args()

    Input = sub(args.input)

    if not args.output:
        args.output = os.path.splitext(args.input)[0] + '.docx'

    if args.diy:
        args.output = "conf/diy_template.docx"
        cmd = f"pandoc -o {args.output} --print-default-data-file reference.docx"
        print("需要另存为.docx一次，才能使用一些高级功能，如：主题")
    else:
        cmd = f"pandoc --defaults={args.defaults} --resource-path='{os.path.dirname(args.input)}' '{Input}' -o '{args.output}'"
        print(cmd)
    os.system(cmd)

    yn = input(f"📂 Open {args.output} [Y/n]: ")
    if yn.lower() in ["", "y"]:
        webbrowser.open(args.output)


if __name__ == "__main__":
    main()
