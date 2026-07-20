import re

TOKEN_RE = re.compile(r"\{\{(.*?)\}(?:<[^>]*>|\s)*\}", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def sanitize(s):
    def repl(m):
        inner = TAG_RE.sub("", m.group(1)).strip()
        result = "{{ " + inner + " }}"
        print("MATCH:", repr(m.group(0)), "-> REPL:", repr(result))
        return result

    return TOKEN_RE.sub(repl, s)


def run():
    BROKEN = (
        '<p>Dear {{<span style="background-color:rgb(255,255,255);'
        'color:rgb(102,102,102);">user.get_full_name}</span>},</p>'
        "<p>It's been five years since you graduated from "
        "{{chapter.school}}!</p>"
    )
    out = sanitize(BROKEN)
    print("OUT_REPR:", repr(out))
