import re

from enum import Enum
from typing import List, Iterator, Union, Optional, Sequence

import dataclasses
from dataclasses import dataclass

from spyll.hunspell import data
from spyll.hunspell.data.aff import Flag
import spyll.hunspell.algo.capitalization as cap
import spyll.hunspell.algo.permutations as pmt

CompoundPos = Enum('CompoundPos', 'BEGIN MIDDLE END')

NUMBER_REGEXP = re.compile(r'^\d+(\.\d+)?$')


@dataclass
class WordForm:
    text: str
    stem: str
    prefix: Optional[data.aff.Prefix] = None
    suffix: Optional[data.aff.Suffix] = None
    prefix2: Optional[data.aff.Prefix] = None
    suffix2: Optional[data.aff.Suffix] = None
    root: Optional[data.dic.Word] = None

    def replace(self, **changes):
        return dataclasses.replace(self, **changes)

    def is_base(self):
        return not self.suffix and not self.prefix

    def flags(self):
        flags = self.root.flags if self.root else set()
        if self.prefix:
            flags = flags.union(self.prefix.flags)
        if self.suffix:
            flags = flags.union(self.suffix.flags)

        return flags

    def all_affixes(self):
        return list(filter(None, [self.prefix2, self.prefix, self.suffix, self.suffix2]))


Compound = List[WordForm]


class Lookup:
    def __init__(self, aff: data.aff.Aff, dic: data.dic.Dic):
        self.aff = aff
        self.dic = dic
        self.collation = cap.Collation(sharp_s=self.aff.CHECKSHARPS, dotless_i=self.aff.LANG in ['tr', 'az', 'crh'])

    def __call__(self, word: str, *,
                 capitalization=True,
                 allow_nosuggest=True,
                 allow_break=True) -> bool:

        def is_correct(variant):
            return any(self.good_forms(variant, capitalization=capitalization, allow_nosuggest=allow_nosuggest))

        if self.aff.FORBIDDENWORD and self.dic.has_flag(word, self.aff.FORBIDDENWORD, for_all=True):
            return False

        if self.aff.ICONV:
            word = self.aff.ICONV(word)

        # print(list(word))
        if self.aff.IGNORE:
            word = word.translate(str.maketrans('', '', self.aff.IGNORE))
            # print(list(word))

        # Numbers are allowed and considered "good word" always
        # TODO: check in hunspell's code, if there are some exceptions?..
        if NUMBER_REGEXP.fullmatch(word):
            return True

        if is_correct(word):
            return True

        if not allow_break:
            return False

        for parts in self.try_break(word):
            if all(is_correct(part) for part in parts if part):
                return True

        return False

    def try_break(self, text, depth=0):
        if depth > 10:
            return

        yield [text]
        for pat in self.aff.BREAK:
            for m in re.finditer(pat.regexp, text):
                start = text[:m.start(1)]
                rest = text[m.end(1):]
                for breaking in self.try_break(rest, depth=depth+1):
                    yield [start, *breaking]

    def good_forms(self, word: str, *,
                   capitalization=True,
                   allow_nosuggest=True) -> Iterator[Union[WordForm, Compound]]:

        if capitalization:
            captype, variants = self.collation.variants(word)
        else:
            captype = cap.guess(word)
            variants = [word]

        for variant in variants:
            yield from self.word_forms(variant, captype=captype, allow_nosuggest=allow_nosuggest)
            yield from self.compounds(variant, captype=captype, allow_nosuggest=allow_nosuggest)

    def word_forms(self,
                   word: str,
                   captype: cap.Cap,
                   prefix_flags: List[Flag] = [],
                   suffix_flags: List[Flag] = [],
                   forbidden_flags: List[Flag] = [],
                   compoundpos: Optional[CompoundPos] = None,
                   allow_nosuggest=True,
                   with_forbidden=False) -> Iterator[WordForm]:

        def is_good_form(form, **kwarg):
            return self.is_good_form(form, compoundpos=compoundpos,
                                     captype=captype,
                                     allow_nosuggest=allow_nosuggest,
                                     **kwarg)

        for form in self.try_affix_forms(word, compoundpos=compoundpos,
                                         prefix_flags=prefix_flags, suffix_flags=suffix_flags,
                                         forbidden_flags=forbidden_flags):
            found = False
            # Base (no suffixes) homonym is allowed if exists.
            # And if it would not, we would not be here at all.
            if compoundpos or not form.is_base():
                if not with_forbidden and self.dic.has_flag(form.stem, self.aff.FORBIDDENWORD):
                    return

            for homonym in self.dic.homonyms(form.stem):
                candidate = form.replace(root=homonym)
                if is_good_form(candidate):
                    found = True
                    yield candidate

            # If it then might be required by compound end to be capitalized, we should find it EVEN
            # if the check is "without checking different capitalizations"
            if self.aff.FORCEUCASE and captype == cap.Cap.INIT and compoundpos == CompoundPos.BEGIN:
                for homonym in self.dic.homonyms(form.stem.lower()):
                    candidate = form.replace(root=homonym)
                    if is_good_form(candidate):
                        found = True
                        yield candidate

            if not found and not compoundpos:
                for homonym in self.dic.homonyms(form.stem, ignorecase=True):
                    candidate = form.replace(root=homonym)
                    if is_good_form(candidate, check_cap=True):
                        yield candidate

    def compounds(self, word: str, captype: cap.Cap, allow_nosuggest=True) -> Iterator[Compound]:
        if self.aff.COMPOUNDBEGIN or self.aff.COMPOUNDFLAG:
            for compound in self.compounds_by_flags(word, captype=captype, allow_nosuggest=allow_nosuggest):
                if not self.is_bad_compound(compound, captype):
                    yield compound

        if self.aff.COMPOUNDRULE:
            for compound in self.compounds_by_rules(word, allow_nosuggest=allow_nosuggest):
                if not self.is_bad_compound(compound, captype):
                    yield compound

    def is_good_form(self,
                     form: WordForm,
                     compoundpos: Optional[CompoundPos],
                     captype: cap.Cap,
                     allow_nosuggest=True,
                     check_cap=False) -> bool:

        aff = self.aff

        # Shouldn't happen, just to make mypy happy (to not complain "if root is None, you can't take its flags" below)
        if not form.root:
            return False

        root_flags = form.root.flags
        all_flags = form.flags()
        root_capitalization = cap.guess(form.root.stem)

        # investigate = (form.prefix and form.prefix.flag == 'D' and form.suffix and form.suffix.flag == 'A')

        if not allow_nosuggest and aff.NOSUGGEST in root_flags:
            return False

        # Check capitalization
        if captype != root_capitalization:
            if aff.KEEPCASE in root_flags and not aff.CHECKSHARPS:
                return False
            # If the dictionary word is not lowercase, we accept only exactly that
            # case, or ALLCAPS
            if check_cap and captype != cap.Cap.ALL and root_capitalization != cap.Cap.NO:
                return False

        # Check affix flags

        if aff.NEEDAFFIX:
            if aff.NEEDAFFIX in root_flags and form.is_base():
                return False
            if not form.is_base() and all(aff.NEEDAFFIX in a.flags for a in form.all_affixes()):
                return False

        if form.prefix and form.prefix.flag not in all_flags:
            return False
        if form.suffix and form.suffix.flag not in all_flags:
            return False

        if aff.CIRCUMFIX:
            if form.suffix and aff.CIRCUMFIX in form.suffix.flags and \
               not (form.prefix and aff.CIRCUMFIX in form.prefix.flags):
                return False

            if form.prefix and aff.CIRCUMFIX in form.prefix.flags and \
               not (form.suffix and aff.CIRCUMFIX in form.suffix.flags):
                return False

        # Check compound flags

        if not compoundpos:
            return aff.ONLYINCOMPOUND not in all_flags
        if aff.COMPOUNDFLAG in all_flags:
            return True
        if compoundpos == CompoundPos.BEGIN:
            return aff.COMPOUNDBEGIN in all_flags
        if compoundpos == CompoundPos.END:
            return aff.COMPOUNDEND in all_flags
        if compoundpos == CompoundPos.MIDDLE:
            return aff.COMPOUNDMIDDLE in all_flags
        # shoulnd't happen
        return False

    # Affixes-related algorithms
    # --------------------------

    def try_affix_forms(self,
                        word: str,
                        prefix_flags: List[Flag],
                        suffix_flags: List[Flag],
                        forbidden_flags: List[Flag],
                        compoundpos: Optional[CompoundPos] = None) -> Iterator[WordForm]:

        yield WordForm(word, word)    # "Whole word" is always existing option

        aff = self.aff

        suffix_allowed = compoundpos in [None, CompoundPos.END] or aff.COMPOUNDPERMITFLAG
        prefix_allowed = compoundpos in [None, CompoundPos.BEGIN] or aff.COMPOUNDPERMITFLAG

        if suffix_allowed:
            yield from self.desuffix(word, required_flags=suffix_flags, forbidden_flags=forbidden_flags)

        if prefix_allowed:
            for form in self.deprefix(word, required_flags=prefix_flags, forbidden_flags=forbidden_flags):
                yield form

                if suffix_allowed and form.prefix and form.prefix.crossproduct:
                    yield from (
                        form2.replace(text=form.text, prefix=form.prefix)
                        for form2 in self.desuffix(form.stem,
                                                   required_flags=suffix_flags,
                                                   forbidden_flags=forbidden_flags,
                                                   crossproduct=True)
                    )

    def desuffix(self,
                 word: str,
                 required_flags: Sequence[Optional[Flag]] = [],
                 forbidden_flags: Sequence[Optional[Flag]] = [],
                 nested: bool = False,
                 crossproduct: bool = False) -> Iterator[WordForm]:

        def good_suffix(suffix):
            return (not crossproduct or suffix.crossproduct) and \
                    all(f in suffix.flags for f in required_flags) and \
                    all(f not in suffix.flags for f in forbidden_flags)

        possible_suffixes = (
            suffix
            for suffix in self.aff.suffixes_index.lookup(word[::-1])
            if good_suffix(suffix) and suffix.lookup_regexp.search(word)
        )

        for suffix in possible_suffixes:
            stem = suffix.replace_regexp.sub(suffix.strip, word)

            yield WordForm(word, stem, suffix=suffix)

            if not nested:  # only one level depth
                for form2 in self.desuffix(stem,
                                           required_flags=[suffix.flag, *required_flags],
                                           forbidden_flags=forbidden_flags,
                                           nested=True,
                                           crossproduct=crossproduct):
                    yield form2.replace(suffix2=suffix, text=word)

    def deprefix(self,
                 word: str,
                 required_flags: Sequence[Optional[Flag]] = [],
                 forbidden_flags: Sequence[Optional[Flag]] = [],
                 nested: bool = False) -> Iterator[WordForm]:

        def good_prefix(prefix):
            return all(f in prefix.flags for f in required_flags) and \
                   all(f not in prefix.flags for f in forbidden_flags)

        possible_prefixes = (
            prefix
            for prefix in self.aff.prefixes_index.lookup(word)
            if good_prefix(prefix) and prefix.lookup_regexp.search(word)
        )

        for prefix in possible_prefixes:
            stem = prefix.lookup_regexp.sub(prefix.strip, word)

            yield WordForm(word, stem, prefix=prefix)

            # TODO: Only if compoundpreffixes are allowed in *.aff
            if not nested:  # only one level depth
                for form2 in self.deprefix(stem,
                                           required_flags=[prefix.flag, *required_flags],
                                           forbidden_flags=forbidden_flags,
                                           nested=True):
                    yield form2.replace(prefix2=prefix, text=word)

    # Compounding details
    # -------------------

    def compounds_by_flags(self,
                           word_rest: str,
                           prev_parts: List[WordForm] = [],
                           *,
                           captype: cap.Cap,
                           allow_nosuggest=True) -> Iterator[List[WordForm]]:

        aff = self.aff
        forbidden_flags = compact(aff.COMPOUNDFORBIDFLAG)
        permitflags = compact(aff.COMPOUNDPERMITFLAG)
        prefix_flags = {
            CompoundPos.BEGIN: [],
            CompoundPos.MIDDLE: permitflags,
            CompoundPos.END: permitflags,
        }
        suffix_flags = {
            CompoundPos.BEGIN: [],
            CompoundPos.MIDDLE: permitflags,
            CompoundPos.END: permitflags,
        }

        # If it is middle of compounding process "the rest of the word is the whole last part" is always
        # possible
        if prev_parts:
            for form in self.word_forms(word_rest,
                                        captype=captype,
                                        compoundpos=CompoundPos.END,
                                        prefix_flags=permitflags,
                                        forbidden_flags=forbidden_flags,
                                        allow_nosuggest=allow_nosuggest):
                yield [form]
        else:
            # if we try to decompoun "forbiddenword's", AND "forbiddenword" with suffix "'s" is forbidden,
            # we shouldn't even try.
            if aff.FORBIDDENWORD and any(aff.FORBIDDENWORD in candidate.flags()
                                         for candidate in
                                         self.word_forms(word_rest, captype=captype, with_forbidden=True)):
                return

        if len(word_rest) < aff.COMPOUNDMIN * 2 or \
                (aff.COMPOUNDWORDMAX and len(prev_parts) >= aff.COMPOUNDWORDMAX):
            return

        compoundpos = CompoundPos.BEGIN if not prev_parts else CompoundPos.MIDDLE

        for pos in range(aff.COMPOUNDMIN, len(word_rest) - aff.COMPOUNDMIN + 1):
            beg = word_rest[0:pos]
            rest = word_rest[pos:]

            for form in self.word_forms(beg, captype=captype, compoundpos=compoundpos,
                                        prefix_flags=prefix_flags[compoundpos],
                                        suffix_flags=suffix_flags[compoundpos],
                                        forbidden_flags=forbidden_flags,
                                        allow_nosuggest=allow_nosuggest):
                parts = [*prev_parts, form]
                for others in self.compounds_by_flags(rest, parts, captype=captype,
                                                      allow_nosuggest=allow_nosuggest):
                    yield [form, *others]

            if aff.SIMPLIFIEDTRIPLE and beg[-1] == rest[0]:
                # FIXME: for now, we only try duplicating the first word's letter
                for form in self.word_forms(beg + beg[-1], captype=captype, compoundpos=compoundpos,
                                            prefix_flags=prefix_flags[compoundpos],
                                            suffix_flags=suffix_flags[compoundpos],
                                            forbidden_flags=forbidden_flags,
                                            allow_nosuggest=allow_nosuggest):
                    parts = [*prev_parts, form]
                    for others in self.compounds_by_flags(rest, parts, captype=captype,
                                                          allow_nosuggest=allow_nosuggest):
                        yield [form.replace(text=beg), *others]

    def compounds_by_rules(self,
                           word_rest: str,
                           prev_parts: List[data.dic.Word] = [],
                           rules: Optional[List[data.aff.CompoundRule]] = None,
                           allow_nosuggest=True) -> Iterator[List[WordForm]]:

        aff = self.aff
        # initial run
        if rules is None:
            rules = self.aff.COMPOUNDRULE

        # FIXME: ignores flags like FORBIDDENWORD and nosuggest

        # If it is middle of compounding process "the rest of the word is the whole last part" is always
        # possible
        if prev_parts:
            for homonym in self.dic.homonyms(word_rest):
                parts = [*prev_parts, homonym]
                flag_sets = [w.flags for w in parts]
                if any(r.fullmatch(flag_sets) for r in rules):
                    yield [WordForm(word_rest, word_rest)]

        if len(word_rest) < aff.COMPOUNDMIN * 2 or \
                (aff.COMPOUNDWORDMAX and len(prev_parts) >= aff.COMPOUNDWORDMAX):
            return

        for pos in range(aff.COMPOUNDMIN, len(word_rest) - aff.COMPOUNDMIN + 1):
            beg = word_rest[0:pos]
            for homonym in self.dic.homonyms(beg):
                parts = [*prev_parts, homonym]
                flag_sets = [w.flags for w in parts]
                compoundrules = [r for r in rules if r.partial_match(flag_sets)]
                if compoundrules:
                    by_rules = self.compounds_by_rules(word_rest[pos:], rules=compoundrules, prev_parts=parts)
                    for rest in by_rules:
                        yield [WordForm(beg, beg), *rest]

    def is_bad_compound(self, compound, captype):
        aff = self.aff

        if aff.FORCEUCASE and captype not in [cap.Cap.ALL, cap.Cap.INIT]:
            if self.dic.has_flag(compound[-1].text, aff.FORCEUCASE):
                return True

        for idx, left_paradigm in enumerate(compound[:-1]):
            left = left_paradigm.text
            right_paradigm = compound[idx+1]
            right = right_paradigm.text

            if aff.COMPOUNDFORBIDFLAG:
                # We don't check right: compoundforbid prohibits words at the beginning and middle
                if self.dic.has_flag(left, aff.COMPOUNDFORBIDFLAG):
                    return True

            if any(self.word_forms(left + ' ' + right, captype=captype)):
                return True

            if aff.CHECKCOMPOUNDREP:
                for candidate in pmt.replchars(left + right, aff.REP):
                    if isinstance(candidate, str) and any(self.word_forms(candidate, captype=captype)):
                        return True

            if aff.CHECKCOMPOUNDTRIPLE:
                if len(set(left[-2:] + right[:1])) == 1 or len(set(left[-1:] + right[:2])) == 1:
                    return True

            if aff.CHECKCOMPOUNDCASE:
                right_c = right[0]
                left_c = left[-1]
                if (right_c == right_c.upper() or left_c == left_c.upper()) and right_c != '-' and left_c != '-':
                    return True

            if aff.CHECKCOMPOUNDPATTERN:
                if any(pattern.match(left_paradigm, right_paradigm) for pattern in aff.CHECKCOMPOUNDPATTERN):
                    return True

            if aff.CHECKCOMPOUNDDUP:
                # duplication only forbidden at the end (TODO: check, that's what I guess from test)
                if left == right and idx == len(compound) - 2:
                    return True

        return False


def compact(*args):
    return [*filter(None, args)]
