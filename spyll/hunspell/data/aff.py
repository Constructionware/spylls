import re
import functools
import itertools

from dataclasses import dataclass, field
from typing import List, Set, Dict, Tuple, Optional, NewType

Flag = NewType('Flag', str)

@dataclass
class Affix:
    flag: Flag
    crossproduct: bool
    strip: str
    add: str
    condition: str
    flags: Set[Flag] = field(default_factory=set)

@dataclass
class Prefix(Affix):
    def __post_init__(self):
        cond_parts = re.findall(r'(\[.+\]|[^\[])', self.condition)
        if self.strip: cond_parts = cond_parts[len(self.strip):]
        if cond_parts and cond_parts != ['.']:
            cond = '(?=' + ''.join(cond_parts) + ')'
        else:
            cond = ''
        self.regexp = re.compile('^' + self.add + cond)

@dataclass
class Suffix(Affix):
    def __post_init__(self):
        cond_parts = re.findall(r'(\[.+\]|[^\[])', self.condition)
        if self.strip: cond_parts = cond_parts[:-len(self.strip)]
        if cond_parts and cond_parts != ['.']:
            cond = '(?<=' + ''.join(cond_parts) + ')'
        else:
            cond = ''
        self.regexp = re.compile(cond + self.add + '$')

@dataclass
class CompoundRule:
    text: str
    def __post_init__(self):
        # TODO: proper flag parsing! Long is (aa)(bb)*(cc), numeric is (1001)(1002)*(1003)
        self.flags = set(re.sub(r'[\*\?]', '', self.text))
        parts = re.findall(r'[^*?][*?]?', self.text)
        self.re = re.compile(self.text)
        self.partial_re = re.compile(functools.reduce(lambda res, part: f"{part}({res})?", parts[::-1]))

    def fullmatch(self, flag_sets):
        relevant_flags = [self.flags.intersection(f) for f in flag_sets]
        return any(
            self.re.fullmatch(''.join(fc))
            for fc in itertools.product(*relevant_flags)
        )

    def partial_match(self, flag_sets):
        relevant_flags = [self.flags.intersection(f) for f in flag_sets]
        return any(
            self.partial_re.fullmatch(''.join(fc))
            for fc in itertools.product(*relevant_flags)
        )

class Leaf:
    def __init__(self):
        self.payloads = []
        self.children = {}

class FSA:
    def __init__(self, ):
        self.root = Leaf()

    def put(self, path, payload):
        cur = self.root
        for p in path:
            if p in cur.children:
                cur.children[p]
            else:
                cur.children[p] = Leaf()

            cur = cur.children[p]

        cur.payloads.append(payload)

    def lookup(self, path):
        for path, leaf in self.traverse(self.root, path):
            for payload in leaf.payloads: yield payload

    def traverse(self, cur, path, traversed = []):
        yield (traversed, cur)
        if not path or path[0] not in cur.children: return
        for p, leaf in self.traverse(cur.children[path[0]], path[1:], [*traversed, path[0]]):
            yield (p, leaf)

@dataclass
class Aff:
    # General
    set: str='UTF-8'
    flag: str='short' # TODO: Enum of possible values, in fact
    af: List[Tuple[int, Set[str]]] = field(default_factory=list)

    # Suggestions
    key: List[str] = field(default_factory=list) # in reader: "short" array (split by pipe)
    try_: str='' # actually just TRY, but conflicts with Python keyword
    nosuggest: Optional[Flag] = None
    maxcpdsugs: int=0
    rep: List[Tuple[str, str]] = field(default_factory=list)
    map: List[Set[str]] = field(default_factory=list)
    maxdiff: int=-1
    onlymaxdiff: bool=False

    # Stemming
    pfx: List[Prefix] = field(default_factory=list)
    sfx: List[Suffix] = field(default_factory=list)
    circumfix: Optional[Flag] = None
    needaffix: Optional[Flag] = None
    pseudoroot: Optional[Flag] = None
    forbiddenword: Optional[Flag] = None

    # Compounding
    compoundrule: List[str] = field(default_factory=list)
    compoundmin: int=3
    compoundwordsmax: Optional[int]=None
    compoundflag: Optional[Flag] = None
    compoundbegin: Optional[Flag] = None
    compoundmiddle: Optional[Flag] = None
    compoundlast: Optional[Flag] = None
    onlyincompound: Optional[Flag] = None
    compoundpermitflag: Optional[Flag] = None
    compoundforbidflag: Optional[Flag] = None

    # TODO: IO, morphology

    def __post_init__(self):
        self.compoundrules = [CompoundRule(r) for r in self.compoundrule]

        self.suffixes = FSA()
        self.prefixes = FSA()
        for suf in self.sfx:
            self.suffixes.put(suf.add[::-1], suf)

        for pref in self.pfx:
            self.prefixes.put(pref.add, pref)
