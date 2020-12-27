"""parser logic for micro files"""
import logging

from ergaleia import load_lines_from_path
from ergaleia import to_args
from ergaleia import un_comment
from fsm.parser import Parser as parser


log = logging.getLogger(__name__)


class IncompleteDirective(Exception):
    """exception for directives without args"""
    def __init__(self, file, linenum):
        super().__init__(f'incomplete directive at line {linenum} of {file}')


class UnexpectedDirective(Exception):
    """exception for unexpected micro directives"""
    def __init__(self, directive, file, linenum):
        super().__init__(
            f"unexpected directive '{directive}' at line {linenum} of {file}"
        )


class ParseError(Exception):
    """exception for parser errors"""
    def __init__(self, msg, file, linenum):
        super().__init__(
            f"parse error: '{msg}' at line {linenum} of {file}"
        )


def trace(*args):
    """trace function for parser"""
    log.debug('TRACE: %s', args)


def parse(path):
    """parse micro file"""
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
        try:
            handled = fsm.handle(directive.lower(), *args, **kwargs)
        except Exception as ex:
            raise ParseError(str(ex), path, linenum)
        if not handled:
            raise UnexpectedDirective(directive, path, linenum)
    return fsm.context.database, fsm.context.servers, fsm.context.tasks


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    print(parse('micro'))
