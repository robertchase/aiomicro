"""parser logic for micro files"""
import logging

from aiomicro.util import load_lines_from_path
from aiomicro.util import to_args
from aiomicro.util import un_comment

from aiomicro.micro.action import STATES


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
    parser = Parser()
    for linenum, line in enumerate(load_lines_from_path(path), start=1):
        line = un_comment(line).strip()
        if not line:
            continue
        toks = line.split(' ', 1)
        if len(toks) == 1:
            raise IncompleteDirective(path, linenum)
        directive, line = toks
        args, kwargs = to_args(line)
        try:
            handled = parser.handle(directive.lower(), *args, **kwargs)
        except Exception as ex:
            raise ParseError(str(ex), path, linenum) from ex
        if not handled:
            raise UnexpectedDirective(directive, path, linenum)
    return parser.database, parser.servers, parser.tasks


class Parser:  # pylint: disable=too-few-public-methods
    # pylint: disable=too-many-instance-attributes
    """Container for micro data"""

    def __init__(self):
        self.database = {}
        self.groups = {}
        self.wraps = {}
        self.tasks = {}
        self.servers = []
        self.server = None
        self.route = None
        self.method = None

        self._state = STATES["INIT"]

    def handle(self, directive, *args, **kwargs):
        """handle directive in the current state"""
        try:
            action, next_state = self._state[directive]
        except KeyError:
            return False
        if action:
            action(self, *args, **kwargs)
        if next_state:
            self._state = STATES[next_state]
        return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    print(parse('micro')[0])
