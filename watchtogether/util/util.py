import os
import random
import string

def random_string(length):
    letters = string.ascii_lowercase
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def rm_f(filename):
    try:
        os.unlink(filename)
    except FileNotFoundError:
        pass
    except TypeError:
        pass


