import re
import os.path
from collections import Counter

from spyll.hunspell.dictionary import Dictionary

def readlist(path):
    if not os.path.isfile(path):
        return []
    # we ignore "incomplete tokenization" feature
    return [ln for ln in open(path).read().splitlines() if ln[-1:] != '.']

def test(name):
    path = f'tests/fixtures/hunspell-orig/{name}'
    dictionary = Dictionary(path)
    bad = readlist(path + '.wrong')
    sug = list(map(lambda s: re.split(r',\s*', s), readlist(path + '.sug')))
    return [
        {
            'word': word,
            'expected': sug[i] if i < len(sug) and sug[i][0] != '' else [],
            'got': list(dictionary.suggest(word))
        } for i, word in enumerate(bad)
    ]

def report(name):
    result = test(name)
    counter = Counter()
    out = []
    for data in result:
        if data['expected'] == data['got']:
            # print(f"  {data['word']}: +")
            counter['good'] += 1
        else:
            out.append(f"  {data['word']}: {data['expected']} vs {data['got']}")
            counter['bad'] += 1

    print(f"{name}: {counter['good']} OK, {counter['bad']} fails")
    print("\n".join(out))

report('base')
report('base_utf')

report('sug')
report('sugutf')

report('sug2')

report('map')
report('maputf')

report('rep')
report('reputf')

report('ngram_utf_fix')

report('IJ')

report('1463589')
report('1463589_utf')
report('1695964')
report('i35725')
report('i54633')
report('i58202')

# report('checksharps') -- CHECKSHARPS+KEEPCASE means "upcase sharp s" is prohibited :facepalm:
# report('checksharpsutf')

# report('allcaps')
# report('allcaps2')
# report('allcaps_utf')
# report('breakdefault')
# report('forceucase')
# report('keepcase')
report('nosuggest')
report('onlyincompound')
# report('opentaal_forbiddenword1')
# report('opentaal_forbiddenword2')
# report('opentaal_keepcase')

# report('ph')
# report('ph2')
# report('phone')

# report('oconv')
# report('utf8_nonbmp')
