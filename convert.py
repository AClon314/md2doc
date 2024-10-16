#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import argparse


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

    if not args.output:
        args.output = os.path.splitext(args.input)[0] + '.docx'

    if args.diy:
        args.output="conf/diy_template.docx"
        cmd = f"pandoc -o {args.output} --print-default-data-file reference.docx"
        print("需要另存为.docx一次，才能使用一些高级功能，如：主题")
    else:
        cmd = f"pandoc --defaults={args.defaults} {args.input} -o {args.output}"
        print(cmd)
    os.system(cmd)

    yn = input(f"📂 Open {args.output} [Y/n]: ")
    if yn.lower() in ["", "y"]:
        os.system(f"open {args.output}")


if __name__ == "__main__":
    main()
