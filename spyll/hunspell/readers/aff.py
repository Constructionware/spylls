import re
import itertools
from dataclasses import dataclass, field
import dataclasses
from typing import Dict

from spyll.hunspell.readers import FileReader
from spyll.hunspell.data import Aff
from spyll.hunspell.data import aff


# Outdated directive names
SYNONYMS = {'PSEUDOROOT': 'NEEDAFFIX', 'COMPOUNDLAST': 'COMPOUNDEND'}


@dataclass
class Context:
    encoding: str = 'Windows-1252'
    flag_format: str = 'short'
    flag_synonyms: Dict[str, str] = field(default_factory=dict)
    ignore: str = ''

    def parse_flag(self, string):
        return self.parse_flags(string)[0]

    def parse_flags(self, string):
        if string is None:
            return []

        if re.match(r'^\d+', string) and self.flag_synonyms:
            return self.flag_synonyms[string]

        # TODO: what if string format doesn't match expected (odd number of chars for long, etc.)?
        if self.flag_format == 'short':
            return string
        elif self.flag_format == 'long':
            return re.findall(r'..', string)
        elif self.flag_format == 'num':
            return re.findall(r'\d+(?=,|$)', string)
        elif self.flag_format == 'UTF-8':
            return string
        else:
            raise ValueError(f"Unknown flag format {self.flag_format}")


def read_aff(path_or_io):
    source = FileReader(path_or_io)
    data = {'SFX': {}, 'PFX': {}, 'FLAG': 'short'}
    context = Context()

    for (num, line) in source:
        directive, value = read_directive(source, line, context=context)

        if not directive:
            continue

        if directive in ['SFX', 'PFX']:
            data[directive][value[0].flag] = value
        else:
            data[directive] = value

        # Additional actions, changing further reading behavior
        if directive == 'FLAG':
            context.flag_format = value
        elif directive == 'AF':
            context.flag_synonyms = value
        elif directive == 'SET':
            context.encoding = value
            source.reset_encoding(value)
        elif directive == 'IGNORE':
            context.ignore = value

        if directive == 'FLAG' and value == 'UTF-8':
            context.encoding = 'UTF-8'
            data['SET'] = 'UTF-8'
            source.reset_encoding('UTF-8')

    return (Aff(**data), context)


def read_directive(source, line, *, context):
    name, *arguments = re.split(r'\s+', line)

    # base_utf has lines like McDonalds’sá/w -- at the end...
    # TODO: Check what's hunspell's logic to deal with this
    if not re.match(r'^[A-Z]+$', name):
        return (None, None)

    name = SYNONYMS.get(name, name)

    value = read_value(source, name, *arguments, context=context)

    return (name, value)


def read_value(source, directive, *values, context):
    value = values[0] if values else None

    def _read_array(count=None):
        if not count:
            count = int(value)

        # TODO: handle if fetching it we'll find something NOT starting with teh expected directive name
        return [
            re.split(r'\s+', ln)[1:]
            for num, ln in itertools.islice(source, count)
        ]

    if directive in ['SET', 'FLAG', 'KEY', 'TRY', 'WORDCHARS', 'IGNORE', 'LANG']:
        return value
    elif directive in ['MAXDIFF', 'MAXNGRAMSUGS', 'MAXCPDSUGS', 'COMPOUNDMIN', 'COMPOUNDWORDMAX']:
        return int(value)
    elif directive in ['NOSUGGEST', 'KEEPCASE', 'CIRCUMFIX', 'NEEDAFFIX', 'FORBIDDENWORD', 'WARN',
                       'COMPOUNDFLAG', 'COMPOUNDBEGIN', 'COMPOUNDMIDDLE', 'COMPOUNDEND',
                       'ONLYINCOMPOUND',
                       'COMPOUNDPERMITFLAG', 'COMPOUNDFORBIDFLAG', 'FORCEUCASE']:
        return aff.Flag(context.parse_flag(value))
    elif directive in ['COMPLEXPREFIXES', 'FULLSTRIP', 'NOSPLITSUGS', 'CHECKSHARPS',
                       'CHECKCOMPOUNDCASE', 'CHECKCOMPOUNDDUP', 'CHECKCOMPOUNDREP', 'CHECKCOMPOUNDTRIPLE',
                       'SIMPLIFIEDTRIPLE']:
        # Presense of directive always means "turn it on"
        return True
    elif directive in ['BREAK', 'COMPOUNDRULE']:
        return [first for first, *_ in _read_array()]
    elif directive in ['REP', 'ICONV', 'OCONV']:
        return [tuple(ln) for ln in _read_array()]
    elif directive in ['MAP']:
        return [
            [
                re.sub(r'[()]', '', s)
                for s in re.findall(r'(\([^()]+?\)|[^()])', ln[0])
            ]
            for ln in _read_array()
        ]
    elif directive in ['SFX', 'PFX']:
        flag, crossproduct, count = values
        return [
            make_affix(directive, flag, crossproduct, *line, context=context)
            for line in _read_array(int(count))
        ]
    elif directive == 'CHECKCOMPOUNDPATTERN':
        return [
            (left, right, rest[0] if rest else None)
            for left, right, *rest in _read_array()
        ]
    elif directive == 'AF':
        return {
            str(i + 1): {*context.parse_flags(ln[0])}
            for i, ln in enumerate(_read_array())
        }
    elif directive == 'AM':
        return {
            str(i + 1): {*ln}
            for i, ln in enumerate(_read_array())
        }
    elif directive == 'COMPOUNDSYLLABLE':
        return (int(values[0]), values[1])
    else:
        # TODO: Maybe for ver 0.0.1 it is acceptable to just not recognize some flags?
        raise Exception(f"Can't parse {directive}")


def make_affix(kind, flag, crossproduct, _, strip, add, *rest, context):
    kind_class = aff.Suffix if kind == 'SFX' else aff.Prefix

    # in LibreOffice ar.aff has at least one prefix (Ph) without any condition. Bug?
    cond = rest[0] if rest else ''
    add, _, flags = add.partition('/')
    return kind_class(
        flag=flag,
        crossproduct=(crossproduct == 'Y'),
        strip=('' if strip == '0' else strip),
        add=('' if add == '0' else add.translate(str.maketrans('', '', context.ignore))),
        condition=cond,
        flags={*context.parse_flags(flags)}
    )