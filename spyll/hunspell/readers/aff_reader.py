import re
import dataclasses
import typing as t

from spyll.hunspell.readers import FileReader
from spyll.hunspell.data import Aff
from spyll.hunspell.data import aff

class AffReader:
    FIELDS = {field.name: field for field in dataclasses.fields(Aff)}

    def __init__(self, path_or_io):
        self.source = FileReader(path_or_io)

    def __call__(self):
        data = {}
        for (num, ln) in self.source:
            name, *parts = re.split(r'\s+', ln)
            field = name.lower()
            if field == 'try':
                field = 'try_'
            val = self._read_directive(field, name, *parts)
            if field == 'sfx' or field == 'pfx':
                if not field in data:
                    data[field] = []
                data[field].append(val)
            else:
                data[field] = val

        return Aff(**data)

    def _read_directive(self, field, name, *values):
        f = self.FIELDS[field]
        value = values[0]
        if field == 'key':
            return value.split('|')
        elif field == 'sfx' or field == 'pfx':
            return self._read_affix(field, values)
        elif f.type == int:
            return int(value)
        elif f.type == str:
            if field=='set':
                self.source.reset_encoding(value)
            return value
        elif f.type == aff.Flag:
            return aff.Flag(value)
        elif f.type == t.List[t.Tuple[str, str]]:
            lines = self._read_array(name, int(value))
            return [tuple(ln) for ln in lines]
        elif f.type == t.List[str]:
            return [ln[0] for ln in self._read_array(name, int(value))]
        elif f.type == t.List[t.Tuple[int, t.Set[str]]]:
            lines = self._read_array(name, int(value))
            return [(i + 1, self._parse_flags(ln[0])) for i, ln in enumerate(lines)]
        else:
            return tuple(values)

    def _read_array(self, name, count):
        res = []
        # TODO: handle if there is not that number the <count> specified
        for i in range(int(count)):
            _, ln = self.source.__next__()
            _, *row = re.split(r'\s+', ln)
            res.append(row)
        return res

    def _read_affix(self, kind, values):
        flag, crossproduct, count = values
        lines = self._read_array(kind.upper(), int(count))

        # TODO: additional flags could be present or absent
        variants = [
            aff.AffixVariant(
                strip=('' if strip == '0' else strip),
                add=add,
                condition=cond,
                flags={}
            )
            for _, strip, add, cond in lines
        ]
        kind_class = aff.Suffix if kind == 'sfx' else aff.Prefix
        return kind_class(flag=flag, crossproduct=(crossproduct == 'Y'), variants=variants)

    def _parse_flags(self, string):
        return set(list(string))
