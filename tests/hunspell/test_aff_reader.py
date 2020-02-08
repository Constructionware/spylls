from spyll.hunspell.data import aff as a
from spyll.hunspell.readers import AffReader

def test_everything():
    reader = AffReader('tests/fixtures/everything.aff')
    aff = reader()

    assert aff.set == 'UTF-8'
    assert aff.flag == 'short'

    assert aff.key == ['qwertyuiopå', 'asdfghjklæø', 'zxcvbnm']

    assert aff.circumfix == a.Flag('f')
    assert aff.needaffix == a.Flag('*')
    assert aff.forbiddenword == a.Flag('-')
    assert aff.nosuggest == a.Flag('X')
    assert aff.maxcpdsugs == 0

    assert aff.rep == [
        ("^Ca$", "Ça"),
        ("^l", "l'"),
        ("^d", "d'"),
        ("^n", "n'"),
        ("^s", "s'")
    ]

    assert aff.map == [
        "aàâäAÀÂÄ",
        "eéèêëEÉÈÊË",
        "iîïyIÎÏY",
        "oôöOÔÖ",
        "uùûüUÙÛÜ",
        "cçCÇ"
    ]

    assert aff.af == [
        (1, {'A', 'B'}),
        (2, {'B', 'C'}),
        (3, {'C', 'D'}),
        (4, {'D', 'E'}),
    ]

    assert aff.sfx == [
        a.Suffix(
            flag='H',
            crossproduct=False,
            variants=[
                a.AffixVariant(strip='y', add='ieth', condition='y', flags={}),
                a.AffixVariant(strip='', add='th', condition='[^y]', flags={}),
            ]
        )
    ]

    assert aff.pfx == [
        a.Prefix(
            flag='F',
            crossproduct=True,
            variants=[
                a.AffixVariant(strip='', add='con', condition='.', flags={})
            ]
        )
    ]
