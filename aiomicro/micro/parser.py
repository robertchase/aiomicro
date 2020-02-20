import logging

from ergaleia import load_lines_from_path
from ergaleia import to_args
from ergaleia import un_comment
from fsm.parser import Parser as parser


log = logging.getLogger(__name__)


class IncompleteDirective(Exception):
    def __init__(self, file, linenum):
        super().__init__(f'incomplete directive at line {linenum} of {file}')


class UnexpectedDirective(Exception):
    def __init__(self, directive, file, linenum):
        super().__init__(
            f"unexpected directive '{directive}' at line {linenum} of {file}"
        )


def trace(*args):
    log.debug(f'TRACE: {args}')


def parse(path):
    fsm = parser.load('aiomicro.micro.micro.fsm')
    # fsm.trace = trace
    for linenum, line in enumerate(load_lines_from_path(path), start=1):
        line = un_comment(line).strip()
        if not line:
            continue
        # log.debug(f'{linenum}: {line}')
        toks = line.split(' ', 1)
        if len(toks) == 1:
            raise IncompleteDirective(path, linenum)
        directive, line = toks
        args, kwargs = to_args(line)
        if not fsm.handle(directive.lower(), *args, **kwargs):
            raise UnexpectedDirective(directive, path, linenum)
    return fsm.context.database, fsm.context.servers


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    print(parse('micro'))
