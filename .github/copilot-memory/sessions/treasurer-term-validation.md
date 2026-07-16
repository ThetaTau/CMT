# Task: Treasurer term-date policy validation on Officer Election Report

## Requirement
- Officer Election Report = chapter officer form: `RoleChangeView` + `RoleChangeSelectForm`,
  template `thetatauCMT/templates/forms/officer.html`, URL `forms:officer`.
- Fields: user, role (New Role*), start (Start Date*), end (End Date*). Formset prefix "form".
- Treasurer role value = "treasurer" (core.models CHAPTER_OFFICER).
- Policy: Treasurer term = 1 year beginning in January. Violation = role==treasurer AND
  (start.month != 1 OR end.month != 1).
- On violation: modal w/ policy msg, REQUIRE a reason, allow submit-anyway, then email
  grand.treasurer@thetatau.org + chapter region directors + region email, cc central office.
- Top-of-page note with the policy message.

## Policy message (exact)
"In accordance with Theta Tau Policy and Procedure Manual, the Treasurer of all chapters
shall be elected to hold office for one year, beginning in January."
Violation adds: " Your submission is in violation of this policy."

## STATUS: COMPLETE — all done, forms suite 486 pass/10 skip/0 fail, flake8 clean, check clean.
## Full repo memory entry written to /memories/repo/thetatauCMT-status.md (top).

## Plan / status
- [x] forms.py: const TREASURER_TERM_POLICY_MSG + VIOLATION msg; add field
      `treasurer_term_exception_reason` (hidden, required=False) + clean() on RoleChangeSelectForm.
      Guard w/ `self.fields["role"].disabled` (skip locked existing rows, like clean_user).
      Helper `treasurer_term_violation(role,start,end)` reusable in view.
- [ ] views.py RoleChangeView.formset_valid: after save, for treasurer forms w/ violation+reason,
      send TreasurerTermExceptionNotification.
- [ ] forms/notifications.py: TreasurerTermExceptionNotification(EmailNotification).
- [ ] templates herald html+text treasurer_term_exception.
- [ ] officer.html: top note + modal + JS (intercept submit, detect treasurer+non-Jan, require
      reason, fill hidden fields, resubmit via requestSubmit).
- [ ] tests in forms/tests/test_views.py (+ maybe test_forms.py).

## Key facts
- View post() has NO `action` check → programmatic resubmit is safe.
- herald .send() DOES populate pytest mailoutbox (HTML in email.alternatives).
- region directors: `chapter.region.directors.all()` (User M2M); region generic: `chapter.region.email`.
- Test: officer POST needs form-TOTAL_FORMS/INITIAL_FORMS/MIN_NUM_FORMS/MAX_NUM_FORMS + form-0-*.
  `_add_to_group(user, "officer")`. other_user = UserFactory(chapter=user.chapter).
- Run tests: podman exec thetataucmt_local_django pytest <path> -v --tb=short
- Baseline full suite ~1819 pass / 17 skip / 0 fail.
