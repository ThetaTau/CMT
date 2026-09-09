# Intrested in contributing to the Chapter Management Tool?

#### Below are the steps to follow:

1. Email cmt@thetatau.org expressing your interest, let us know your experience with Django/Python/Webdev and how you would like to help.
2. Meet with a member of CMT team to go over structure and setup instructions.
3. [Follow setup instructions](docs/install.md)
4. Grab and [issue](https://github.com/VenturaFranklin/thetatauCMT/issues) and mark ["in progress"](https://github.com/VenturaFranklin/thetatauCMT/issues?q=is%3Aissue+is%3Aopen+label%3A%22in+progress%22)
5. Work on issue, finish issue
6. Submit pull request

## Security checks on pull requests

Every PR into `main` or `staging` runs [Semgrep](https://semgrep.dev), a static
analysis tool that looks for known-risky code patterns.

It is **diff-aware**: it only looks at the lines your PR changed. Pre-existing
issues elsewhere in the codebase will not block your PR. Your check fails only if
your diff introduces a new **ERROR-severity** finding. Lower-severity findings
show up as comments on the "Files changed" tab but do not block.

On top of the standard Django/Python rule sets, this repo has three of its own
(in `.github/semgrep/cmt.yml`):

- **`cmt-no-eval`**: no new `eval()` / `exec()`. Use a real parser or a safe
  evaluator instead.
- **`cmt-no-new-csrf-exempt`**: a new `@csrf_exempt` view must be justified
  (inbound webhook with signature verification, etc.).
- **`cmt-mark-safe-nonliteral`**: do not call `mark_safe()` on a variable;
  sanitize with `nh3` or build the HTML with `format_html()`.

### Bypassing a finding

If a finding is a false positive or the pattern is genuinely safe in context,
add a `nosemgrep` comment **on the flagged line** with a short reason:

```python
result = eval(formula)  # nosemgrep: cmt-no-eval -- formula is an admin-only config value, validated on save
```

The comment is visible in code review, so a reviewer sees the justification. Use
it sparingly; "make the check pass" is not a reason.

### Running it locally (optional)

Scan with the same rules the CI uses:

```
docker run --rm -v "$PWD:/src" -w /src semgrep/semgrep \
  semgrep scan --config .github/semgrep/ --config p/django --config p/python
```

Or install Semgrep (`pipx install semgrep`) and drop the `docker run ...` prefix.

Following 2 scoops of Django - https://www.feldroy.com/products/two-scoops-of-django-3-x

Entire structure based on Cookie Cutter Django: https://github.com/pydanny/cookiecutter-django

We are still (as of 20210716) on Django 2.2 LTS need to upgrade to 3.2 soon (before March 2022). https://www.djangoproject.com/download/
