#!/usr/bin/env python
# -*- coding: utf-8 -*-
__VERSION__ = 'v0.2.2025.05 from https://github.com/AClon314/md2doc'
import re
import os
import json
import time
import heapq
import logging
from rich.logging import RichHandler
import argparse
import webbrowser
import asyncio as aio
from rich import progress
from collections import UserDict
from typing import Callable, Any, Iterable, Literal, ParamSpec, TypeVar, cast
from platformdirs import user_cache_path
_APPPATH_ = user_cache_path('pandoc')
_JS_PATH_ = os.path.join(_APPPATH_, 'pandoc.json')
PS = ParamSpec('PS')
TV = TypeVar('TV')
IS_DEBUG = os.getenv('DEBUG')
rich_handler = RichHandler(show_time=True, show_path=False, rich_tracebacks=True)
logging.basicConfig(
    level=logging.DEBUG if IS_DEBUG else logging.INFO,
    format="%(message)s",
    handlers=[rich_handler]
)
Log = logging.getLogger(__name__)
PATH_DIY = os.path.join('conf', 'diy_template')
def Alt(t='图'): return ["\n" + t + r"\{\} ?(.*)\n", "\n" + t + "{chapter}-{i} {name}\n"]
def Match(key: str, text: str): return re.search(PATTERN[key][0], text)
def Matches(key: str, text: str): return re.finditer(PATTERN[key][0], text)
def unescape(text: str): return re.sub(r'\\([^n])', r'\1', text)
def push(queue: list, key: str, match: re.Match | None): heapq.heappush(queue, (match.start(), key, match)) if match else None
def dir_filename(path: str): return os.path.dirname(path), os.path.basename(path)
def no_ext(path: str): return os.path.splitext(path)[0]
def _overflow(text: str, overflow=48): return f'{text[:overflow].strip()}🔸{text[-overflow:].strip()}' if len(text) > overflow * 2 else text


def copy_kwargs(
    kwargs_call: Callable[PS, Any]
) -> Callable[[Callable[..., TV]], Callable[PS, TV]]:
    """Decorator does nothing but returning the casted original function"""
    def return_func(func: Callable[..., TV]) -> Callable[PS, TV]:
        return cast(Callable[PS, TV], func)
    return return_func


def unzip(zip: str):
    from zipfile import ZipFile
    To = no_ext(zip)
    with ZipFile(zip, 'r') as zipObj:
        # Extract all the contents of zip file in current directory
        zipObj.extractall(To)
    Log.info(f"📚 Unzip {zip} to {To} 📂")


_PATTERN = {
    'photo': [r"""\n!\[(.*) ?(.*)\]\(([^ \t\r\n]+) ?['"]?(.*)['"]?\)\n""", """
::: {{custom-style="Figure"}}
![图{chapter}-{i} 	 {name}]({url} '图{i} {name} {hint}'){{ width=80% }}
:::
"""],
    'codeFig': [r"<!--(.*?)-->\n```((?=.*mermaid|.*plantuml|.*chartjs).+)\n([\s\S]*?)\n```", """::: {{custom-style="Figure"}}\n```{1}\n{2}\n```\n""" + Alt('图')[1] + ":::"],
    'code': [r"```((?!.*mermaid|.*plantuml|.*chartjs).+)\n([\s\S]*?)```\n", "```{0} {{.numberLines}}\n{1}```\n"],
    '图': Alt('图'),
    'table': [r"<!--(.*?)-->(\n.*\n\| *[:-].*\n[\s\S]*?)\n\n", """\n
::: {{custom-style="Figure"}}
表{chapter}-{i} 	 {0}
{1}
:::
<br>\n\n"""],
    '表': Alt('表'),
    'cite': [r':::::::::::::: \{#refs [^\t]*\n::::::::::::::', ""],
    'csl': [r"\[\\\[(\d+)\\\] \]\{\.csl-left-margin\}", r"\1"]
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
    '表': {
        'name': 0
    }
}
PATTERN: dict[str, tuple[re.Pattern, str]] = {k: (re.compile(v[0]), v[1]) for k, v in _PATTERN.items()}


def same_fullpath(fullpath: str, rename='.pre_{}.md'):
    Dir, file = dir_filename(fullpath)
    filepath = os.path.join(Dir, rename.format(no_ext(file)))
    return filepath


async def popen(
    cmd: str,
    mode: Literal['realtime', 'wait', 'no-wait'] = 'wait',
    Raise=False,
    log: Callable = Log.warning,
    timeout=600,
    **kwargs
):
    """Used on long running commands

    Args:
        mode (str):
            - realtime: **foreground**, print in real-time
            - wait: await until finished
            - no-wait: **background**, immediately return, suitable for **forever-looping**, use:
            p = await popen('cmd', mode='bg')
            await p.expect(pexpect.EOF, async_=True)
            print(p.before.decode().strip())
        kwargs: `pexpect.spawn()` args

    Returns:
        process (pexpect.spawn):
    """
    import sys
    import pexpect
    Log.info(f"{mode}: '{cmd}'")
    p = pexpect.spawn(cmd, timeout=timeout, **kwargs)
    FD = sys.stdout.fileno()
    def os_write(): return os.write(FD, p.read_nonblocking(4096))
    sig = 0
    if mode == 'realtime':
        while p.isalive():
            try:
                os_write()
            except pexpect.TIMEOUT:
                log(f"Timeout: {cmd}")
                p.kill(sig)
                sig = 9
                await aio.sleep(timeout / 2)
            except Exception:
                raise
            await aio.sleep(0.03)
        try:
            os_write()
        except pexpect.EOF:
            pass
    elif mode == 'wait':
        while p.isalive():
            try:
                await p.expect(pexpect.EOF, async_=True)
            except pexpect.TIMEOUT:
                log(f"Timeout: {cmd}")
                p.kill(sig)
                sig = 9
                await aio.sleep(timeout / 2)
            except Exception:
                raise
    elif mode == 'no-wait':
        ...
    else:
        raise ValueError(f"Invalid mode: {mode}")
    if p.exitstatus != 0:
        if Raise:
            raise ChildProcessError(f"{cmd}")
        else:
            log(f'{p.exitstatus} from "{cmd}" → {p.before.decode()}')
    return p


async def pre_process(filename: str, yaml: str | None = None):
    """pre-process markdown file, return pre-processed file path

    Args:
        filename: input markdown file path
        yaml: yaml config file path, which will expand refs/cite/Reference
    """
    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()

    # TODO: use `pandoc-crossref`
    # is_abstract = re.search(r'\n# *[Aa]bstract *\n', text)
    # queue = []
    # push(queue, 'photo', Match('photo', text))
    # push(queue, 'codeFig', Match('codeFig', text))
    # push(queue, '图', Match('图', text))
    # text = _sub_priority(text, queue, ch_offset=-1 if is_abstract else 0)

    match = True
    while match:
        match = re.search(r"(```.*?mermaid.*?\n)(?!%%)", text)
        if not match:
            break
        _1 = match.group(1)
        text = re.sub(_1, _1 + r"%%{ init: { 'theme': 'base', 'themeVariables': { 'primaryColor': '#ffffff', 'primaryTextColor': '#000000', 'secondaryTextColor': '#000000', 'tertiaryTextColor': '#000000' } } }%%\n", text)

    match = True
    while match:
        match = re.search(r"(```.*?plantuml.*?\n@startuml\n)(?!!theme)", text)
        if not match:
            break
        _1 = match.group(1)
        text = re.sub(_1, _1 + '!theme plain\nskinparam defaultFontName "Noto Sans CJK SC"\n', text)

    # TODO: use `pandoc-crossref`
    # queue = []
    # push(queue, 'table', Match('table', text))
    # push(queue, '表', Match('表', text))
    # text = _sub_priority(text, queue)

    # # code block num of lines
    # for m in Matches('code', text):
    #     From, To = From_To(m, 'code', 0, 0)
    #     text = re.sub(From, To, text)

    # pagebreak between chapters
    match = re.findall(r"\n# (.+)\n", text)
    for m in match:
        text = re.sub(rf"\n# {m}\n", r"\n\\pagebreak\n\n# " + m + '\n', text)

    pre_md = same_fullpath(filename)
    # if yaml:
    #     cite = await expand_cite(filename, yaml, pre_md)
    #     text = re.sub(r'\n::: *\{ *#refs[^\t]*\n:::\n', f'\n{cite}\n', text)

    with open(pre_md, 'w', encoding='utf-8') as f:
        f.write(text)
    Log.info(f"💾 Pre-process: {pre_md}")
    return pre_md


async def expand_cite(input: str, yaml: str, output: str | None = None):
    from yaml import safe_load
    if not output:
        output = same_fullpath(input)
    with open(yaml, 'r', encoding='utf-8') as f:
        conf = safe_load(f)
    cite_keys = ['bibliography', 'csl']
    cite_args = {k: conf[k] for k in cite_keys if k in conf.keys()}
    output = await pandoc(input=input, output=output, **cite_args)
    with open(output, 'r', encoding='utf-8') as f:
        text = f.read()

    # with open(input, 'w', encoding='utf-8') as f:
    #     f.write(text)
    # exit(1)

    text = PATTERN['cite'][0].findall(text)
    if text:
        text = text[0]
        cite = PATTERN['csl'][0].sub(_PATTERN['csl'][1] + '. ', text)
    else:
        cite = ''
    return cite


def _sub_priority(text, queue, ch_offset=0):
    idx = 1
    ch_old = 0
    while queue:
        _, key, match = heapq.heappop(queue)
        ch = len(re.findall(r'\n# *[一-龟\w ]+\n', text[:match.start()])) + ch_offset
        if ch != ch_old:
            idx = 1
            ch_old = ch

        From, To = From_To(match, key, ch, idx)
        text = re.sub(From, To, text)
        idx += 1
        if IS_DEBUG:
            From = unescape(From)
            From = _overflow(From)
            To = _overflow(To)
            Log.debug(f"☀️替换：{From} ➡️→ {To}")

        next_match = Match(key, text)
        heapq.heappush(queue, (next_match.start(), key, next_match)) if next_match else None
    return text


def From_To(match: re.Match, key: str, chapter: int, idx: int) -> tuple[str, str]:
    group = list(match.groups())
    rule = RULES.get(key, {})
    kw = {k: group[v] for k, v in rule.items()}
    From = re.escape(match.group())
    # Log.info(len(group), group)
    To = PATTERN[key][1].format(*group, i=idx, chapter=chapter, **kw)
    return From, To


async def pandoc(input: str, output: str, yaml: str | None = None, diy=False, args=[], **kwargs):
    '''return output file path, would ***raise ChildProcessError*** if failed

    Args:
        input: input file path
        output: output file path, **MUST** follow extension name like `.docx`/`.md`...
        yaml: yaml config file path
        diy (bool): generate default pandoc `diy_template.EXT`
        args (list): additional arguments for pandoc command
    '''
    EXT = output.split('.')[-1].lower()
    if diy:
        output = f"{PATH_DIY}.{EXT}"
        cmd = f"pandoc -o {output} --print-default-data-file reference.{EXT}"
        Log.info("💾 需要另存为.docx一次，才能使用一些高级功能，如：主题👔") if 'doc' in EXT else None
    else:
        _defaults = f'--defaults={yaml}' if yaml else ''
        Dir, basename = dir_filename(input)

        # eg: input="in.md", _res_path="./in" if exists else "./"
        _res_path = os.path.join(Dir, no_ext(os.path.basename(input)))
        if not os.path.exists(_res_path):
            _res_path = Dir

        _res_path = f"--resource-path='{_res_path}'" if _res_path else ''
        cmd = f"pandoc {_defaults} --citeproc {_res_path} '{input}' -o '{output}' "
    for k, v in kwargs.items():
        if k and v:
            if isinstance(v, Iterable) and not isinstance(v, str):
                _s = f'--{k}='
                _s += f' --{k}='.join(v)
            else:
                _s = f'--{k}={v}'
            args.append(_s)
    cmd += ' '.join(args)
    p = await popen(cmd)
    return output


class IOdict(UserDict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not os.path.exists(_JS_PATH_):
            self.write({})
        with open(_JS_PATH_, 'r', encoding='utf-8') as f:
            text = f.read(8)
            self.write({}) if not text else None
            f.seek(0)
            self.data = {**json.load(f), **self.data}
        self.write(self.data)

    def __getitem__(self, key):
        if key not in self.data:
            return None
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.write(self.data)

    def __delitem__(self, key):
        super().__delitem__(key)
        self.write(self.data)

    def write(self, text: str | dict):
        if isinstance(text, dict):
            text = json.dumps(text, indent=2, ensure_ascii=False)
        with open(_JS_PATH_, 'w', encoding='utf-8') as f:
            f.write(text)


def init_progress():
    from atexit import register
    global PG
    PG = progress.Progress(
        progress.SpinnerColumn(),
        progress.TextColumn("[progress.description]{task.description}"),
        progress.BarColumn(),
        progress.TextColumn("[progress.percentage]{task.completed:.0f}%"),
        progress.TimeElapsedColumn(),
        progress.TimeRemainingColumn(),
    )
    PG.start()
    register(PG.stop)
    return PG


async def update_timer(tid, per_half_sec=1.0):
    while not PG.tasks[tid].finished:
        await aio.sleep(0.5)
        PG.update(tid, advance=per_half_sec)


async def wrap_pg(coro, Input):
    global LAST_TIME
    _begin = time.time()
    last_time = LAST_TIME[Input]
    describe = _overflow(Input)
    res = None
    if last_time:
        speed = 50 / float(last_time)
        tid = PG.add_task(describe, total=100)
        tasks = [coro, update_timer(tid, speed)]
        for task in aio.as_completed(tasks):
            _res = await task
            if _res:  # 如果是 coro 完成
                res = _res
                PG.remove_task(tid)
                break
            else:  # 如果是 update_timer 完成
                PG.update(tid, description=f"{describe} waiting pandoc")
                PG.stop_task(tid)
                PG.update(tid, completed=0)
    else:
        tid = PG.add_task(describe, total=None)
        res = await coro
        PG.remove_task(tid)
    LAST_TIME[Input] = time.time() - _begin
    return res


async def main():
    global TASKS, LAST_TIME
    os.makedirs(_APPPATH_, exist_ok=True)
    LAST_TIME = IOdict()
    TASKS = {}
    init_progress()
    kwargs = vars(args)
    for Input in args.input:
        if not os.path.exists(Input):
            Log.error(f"❌ 文件不存在: {input}")
            continue
        kwargs['input'] = Input
        if (args.output and '.doc' in args.output) or any(fmt in Input for fmt in ['.md', '.tex']):
            TASKS[Input] = wrap_pg(docx(**kwargs, args=unknown), Input)
        elif (args.output and '.md' in args.output) or any(fmt in Input for fmt in ['.doc', '.htm']):
            TASKS[Input] = wrap_pg(markdown(**kwargs, args=unknown), Input)
        else:
            Log.error("🤔 请指明输出文件类型 Please specify the output file type")
            continue

    # TODO: 多线程
    _output = await aio.gather(*TASKS.values())
    TASKS = {k: v for k, v in zip(TASKS.keys(), _output)}
    PG.stop()

    yn = input(f"📂 Open {TASKS[Input]} [Y/n]: ")
    if yn.lower() in ["", "y"]:
        webbrowser.open(TASKS[Input])


@copy_kwargs(pandoc)
async def markdown(*args, **kwargs):
    input = kwargs.get('input', args[0] if args else None)
    if not input:
        raise ValueError("input file is required")
    output = kwargs.get('output', input)
    output = no_ext(output) + ".md"
    return pandoc(*args, **kwargs)


async def docx(input: str, output: str | None = None, yaml: str | None = None, diy=False, raw=False, args=[], **kwargs):
    Input = input if raw else await pre_process(input, yaml)
    output = output if output else no_ext(input) + ".docx"
    try:
        output = await pandoc(input=Input, output=output, yaml=yaml, diy=diy, args=args, **kwargs)
        if IS_DEBUG:
            unzip(output)
            Log.debug(f"See {os.path.join(no_ext(output), 'word', 'document.xml')}")
    except ChildProcessError:
        diagnose_mermaid()
        Log.error("提示：尝试为plantuml、mermaid内的中文字符，用\"...\"包裹")  # TODO: 仅当plantuml出错时才报错
    return output


def argParse():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=f"""
Markdown.md to .docx/.pptx by pandoc & marpit
Add `DEBUG=1` to show more msg.
cache: {_JS_PATH_}""")
    parser.add_argument("input", nargs="+", default="README.md")
    parser.add_argument("-o", "--output", nargs="?")

    parser.add_argument("-r", "--raw", action="store_true",
                        help=f"No post process, eg: `图{{}} name` → `图1-1 name` will be NOT applied")
    parser.add_argument("--yaml", default="conf/conf.yaml", metavar="conf/conf.yaml",
                        help="Default args in yaml config")
    parser.add_argument("--diy", action="store_true",
                        help="generate default pandoc diy_template.docx")
    args, unknown = parser.parse_known_args()
    return args, unknown


def diagnose_mermaid():
    """find .tmp-pmcf-input-..."""
    import glob
    # 列举cwd下的.tmp-pmcf-input-*中的第1个文件
    pmcf_tmps = glob.glob(os.path.join(os.getcwd(), '.tmp-pmcf-input-*'))
    if pmcf_tmps:
        Log.error("⚠️ mermaid 出错位于这些文件内，请检查:")
        for name in pmcf_tmps:
            Log.error(f'\t{name}')


# snippet main
if __name__ == "__main__":
    # import sys
    Log.info(__VERSION__)
    args, unknown = argParse()
    # sys.stderr = sys.stdout
    aio.run(main())
# snippet main
