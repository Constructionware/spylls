import re
import os.path

from spyll.hunspell.dictionary import Dictionary
# from spyll.hunspell.algo.lookup import analyze

dic = Dictionary('tests/fixtures/hunspell-orig/base')

# print(dic.aff.pfx)
# print(list(analyze(dic.aff, dic.dic, 'foo-bar')))
# print(dic.lookup('foo-baz'))
# print(list(analyze(dic.aff, dic.dic, 'foo-baz')))
# print(dic.aff)
print(dic.lookup('uncreated'))

# print(list(analyze(dic.aff, dic.dic, 'implied')))

