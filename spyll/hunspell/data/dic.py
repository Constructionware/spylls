import itertools
from dataclasses import dataclass
from typing import List, Set

@dataclass
class Word:
    stem: str
    flags: Set[str]
    # TODO: morphology

@dataclass
class Dic:
    words: List[Word]

    def __post_init__(self):
        self.index = {stem: list(words) for stem, words in itertools.groupby(self.words, lambda w: w.stem)}
        self.index_l = {stem.lower(): list(words) for stem, words in itertools.groupby(self.words, lambda w: w.stem)}

    def homonyms(self, word, *, ignorecase=False):
        if ignorecase:
            return self.index_l.get(word, [])
        else:
            return self.index.get(word, [])
