stringy = 'hello!!'
stringy.split('!!')
stringy.split('!!')
stringy.replace('!!', '!!')
stringy.splitlines()
stringy.split('!!')  # tatari-noqa


class FooDisallowedAttr:
    disallowed = True
    allowed = True


f = FooDisallowedAttr()
not_ok = f.disallowed
ok = f.disallowed  # tatari-noqa
