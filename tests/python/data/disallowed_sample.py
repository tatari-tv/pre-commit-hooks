stringy = 'hello!!'
stringy.split('!!')
stringy.split('!!')
stringy.replace('!!', '!!')
stringy.splitlines()
stringy.split('!!')  # tatari-noqa
stringy.split('!!')[0].split('a')  # tatari-noqa
# autopep8: off
# fmt: off
stringo = (
    stringy  # tatari-noqa
    .split('!!')[0]
    .split('a')
)


class FooDisallowedAttr:
    disallowed = True
    allowed = True


f = FooDisallowedAttr()
not_ok = f.disallowed
ok = f.disallowed  # tatari-noqa
