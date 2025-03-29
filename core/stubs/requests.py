from requests.models import Response

class JsonThatReturnsItselfOnKeyWithNoValue(dict):
    def __getitem__(self, key):
        if self._has_no_value_for(key): return self
        return self._value_from_key(key)
    
    def _has_no_value_for(self, key):
        return key not in self
    
    def _value_from_key(self, key):
        return super().__getitem__(key)

class StubOkResponse(Response):
    def __init__(self):
        self.status_code = self.status_code()

    def status_code(self):
        return 200
    
    def json(self):
        return JsonThatReturnsItselfOnKeyWithNoValue()

def get(*args, **kwargs):
    log("get", args, kwargs)
    return StubOkResponse()

def post(*args, **kwargs):
    log("post", args, kwargs)
    return StubOkResponse()

def log(method_name, *args, **kwargs):
    args_list = f"{as_comma_list(args)}, {as_comma_list(kwargs)}"
    print(f"[STUBBED] request.{method_name}({args_list})")

def as_comma_list(args):
    return ','.join(as_list(args))

def as_list(args):
    if type(args) == dict: return [ f"{name}={args[name]}" for name in args ]
    return [ str(arg) for arg in args ]
