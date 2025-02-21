from requests.models import Response

class ResponseJson(dict):
    def __getitem__(self, key):
        if key not in self: return self
        return super().__getitem__(key)

class StubOkResponse(Response):
    DEFAULT_JSON_CONTENTS = {
        "expires_in": 999999999,
        "created_at": 999999999,
        "token_type": "test",
        "access_token": "test"
    }

    def __init__(self):
        self.status_code = self.status_code()

    def status_code(self):
        return 200
    
    def json(self):
        return ResponseJson(StubOkResponse.DEFAULT_JSON_CONTENTS)

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
