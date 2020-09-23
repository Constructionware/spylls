from enum import Enum
from typing import Tuple, List

Cap = Enum('Cap', 'NO INIT ALL HUHINIT HUH')


def guess(word: str) -> Cap:
    if word.lower() == word:
        return Cap.NO
    if word[:1].lower() + word[1:] == word.lower():
        return Cap.INIT
    if word.upper() == word:
        return Cap.ALL
    if word[:1].lower() != word[:1]:
        return Cap.HUHINIT
    return Cap.HUH


def coerce(word: str, cap: Cap) -> str:
    if cap in (Cap.INIT, Cap.HUHINIT):
        return upperfirst(word)
    if cap == Cap.ALL:
        return word.upper()
    return word


def lowerfirst(word: str) -> str:
    return word[0].lower() + word[1:]


def upperfirst(word: str) -> str:
    return word[0].upper() + word[1:]


def lower(word: str) -> str:
    # turkic "lowercase dot i" to latinic "i"
    return word.lower().replace('i̇', 'i')


def capitalize(word: str) -> str:
    return word[0].upper() + lower(word[1:])


def variants(word: str, *, lang_with_dot_i=False) -> Tuple[Cap, List[str]]:
    captype = guess(word)

    was_dot_i = word and word[0] == 'İ'
    allow_lower = not was_dot_i or lang_with_dot_i

    if captype == Cap.NO:
        return (captype, [word])
    if captype == Cap.INIT:
        if allow_lower:
            return (captype, [word, lower(word)])
        return (captype, [word])
    if captype == Cap.HUHINIT:
        if allow_lower:
            return (captype, [word, lowerfirst(word), lower(word), capitalize(word)])
        return (captype, [word, capitalize(word)])
        # TODO: also here and below, consider the theory FooBar meant Foo Bar
    if captype == Cap.HUH:
        return (captype, [word, lower(word)])
    # Cap.ALL:
    if allow_lower:
        return (captype, [word, lower(word), capitalize(word)])
    return (captype, [word, capitalize(word)])


class Collation:
    def __init__(self, sharp_s=False, dotless_i=False):
        self.sharp_s = sharp_s
        self.dotless_i = dotless_i

    def lower(self, word):
        def sharp_s_variants(text, start=0):
            pos = text.find('ss', start)
            if pos == -1:
                return []
            replaced = text[:pos] + 'ß' + text[pos+2:]
            return [replaced, *sharp_s_variants(replaced, pos+1), *sharp_s_variants(text, pos+2)]

        if word[0] == 'İ' and not self.dotless_i:
            return []

        # CHECKSHARPS flag also prohibits uppercase "sharp s"
        if self.sharp_s and 'ß' in word and guess(word.replace('ß', '')) == Cap.ALL:
            return []

        if self.dotless_i:
            lowered = word.translate(str.maketrans('İI', 'iı')).lower()
        else:
            # turkic "lowercase dot i" to latinic "i"
            lowered = word.lower().replace('i̇', 'i')

        if self.sharp_s and 'SS' in word:
            return [*sharp_s_variants(lowered), lowered]

        return [lowered]

    def variants(self, word: str) -> Tuple[Cap, List[str]]:
        captype = guess(word)

        if captype == Cap.NO:
            result = [word]
        elif captype == Cap.INIT:
            result = [word, *self.lower(word)]
        elif captype == Cap.HUHINIT:
            result = [word,
                        *(l + word[1:] for l in self.lower(word[0]))]
            # TODO: also here and below, consider the theory FooBar meant Foo Bar
        elif captype == Cap.HUH:
            result = [word]
        elif captype == Cap.ALL:
            result = [word,
                        *self.lower(word),
                        *(word[0] + lower for lower in self.lower(word[1:]))]

        return (captype, result)
