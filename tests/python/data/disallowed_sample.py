# disallowed functions
stringy = 'hello!!'
stringy.split('!!')
stringy.split('!!')
stringy.replace('!!', '!!')
stringy.splitlines()
stringy.split('!!')  # tatari-noqa

# disallowed attributes
class FooDisallowedAttr:
    disallowed = True
    allowed = True

f = FooDisallowedAttr()
not_ok = f.disallowed
ok = f.disallowed  # tatari-noqa

