# Django Template Refactor - collapsible_filter Migration

## Summary
24 files need refactoring to use new `{% collapsible_filter %}` template tag.
- Add `{% load filter_tags %}` after `{% load crispy_forms_tags %}` in all 24 files
- Replace form blocks with collapsible_filter tag calls

## All Files - Add Load Tag
Pattern to replace in ALL 24 files:
```
{% load crispy_forms_tags %}
{% load static i18n %}
```
With:
```
{% load crispy_forms_tags %}
{% load filter_tags %}
{% load static i18n %}
```

## Category A Files (14) - Replace 3-line form block

### Files 1-13: Standard pattern
Files: ballot_completelist, ballot_list, ballot_votelist, chapter_list, event_list_all, chapter_balances, invoice_list, audit_list, bylaws_list, convention_list, hseducation_list, osm_list, job_list_all

Replace:
```
                        <form method="get" class="form-search d-flex flex-wrap align-items-center ms-md-auto">
                          {% crispy filter.form filter.form.helper %}
                        </form>
```

### File 14: rmp_list.html - FIRST form only
Replace FIRST occurrence only:
```
                        <form method="get" class="form-search d-flex flex-wrap align-items-center ms-md-auto">
                          {% crispy filter.form filter.form.helper %}
                        </form>
```

## Replacements by File

### 1. ballot_completelist.html
Replace load: YES
Form block lines 54-56:
```
                        {% collapsible_filter filter label="Filter Ballots" collapse_id="ballotCompleteFilter" %}
```

### 2. ballot_list.html
Replace load: YES
Form block lines 22-24:
```
                        {% collapsible_filter filter label="Filter Ballots" collapse_id="ballotFilter" %}
```

### 3. ballot_votelist.html
Replace load: YES
Form block lines 12-14:
```
                        {% collapsible_filter filter label="Filter Ballots" collapse_id="ballotVoteFilter" %}
```

### 4. chapter_list.html
Replace load: YES
Form block lines 18-20:
```
                        {% collapsible_filter filter label="Filter Chapters" collapse_id="chapterFilter" %}
```

### 5. event_list_all.html
Replace load: YES
Form block lines 18-20:
```
                        {% collapsible_filter filter label="Filter Events" collapse_id="eventAllFilter" %}
```

### 6. chapter_balances.html
Replace load: YES
Form block lines 17-19:
```
                        {% collapsible_filter filter label="Filter Balances" collapse_id="balanceFilter" %}
```

### 7. invoice_list.html
Replace load: YES
Form block lines 25-27:
```
                        {% collapsible_filter filter label="Filter Invoices" collapse_id="invoiceFilter" %}
```

### 8. audit_list.html
Replace load: YES
Form block lines 18-20:
```
                        {% collapsible_filter filter label="Filter Audits" collapse_id="auditFilter" %}
```

### 9. bylaws_list.html
Replace load: YES
Form block lines 18-20:
```
                        {% collapsible_filter filter label="Filter Bylaws" collapse_id="bylawsFilter" %}
```

### 10. convention_list.html
Replace load: YES
Form block lines 31-33:
```
                        {% collapsible_filter filter label="Filter Conventions" collapse_id="conventionFilter" %}
```

### 11. hseducation_list.html
Replace load: YES
Form block lines 18-20:
```
                        {% collapsible_filter filter label="Filter HS Education" collapse_id="hsEducationFilter" %}
```

### 12. osm_list.html
Replace load: YES
Form block lines 31-33:
```
                        {% collapsible_filter filter label="Filter OSMs" collapse_id="osmFilter" %}
```

### 13. job_list_all.html
Replace load: YES
Form block lines 18-20:
```
                        {% collapsible_filter filter label="Filter Jobs" collapse_id="jobsAllFilter" %}
```

### 14. rmp_list.html
Replace load: YES
Form block lines 18-20 (FIRST form only):
```
                        {% collapsible_filter filter label="Filter RMPs" collapse_id="rmpFilter" %}
```

## Category B Files (4) - Replace form block with commented lines

### 15. event_list.html
Replace load: YES
Replace lines 22-29 (7-line block with commented lines):
```
                        {% collapsible_filter filter label="Filter Events" collapse_id="eventFilter" %}
```

### 16. objective_list.html
Replace load: YES
Replace lines 23-30 (7-line block with commented lines):
```
                        {% collapsible_filter filter label="Filter Goals" collapse_id="goalsFilter" %}
```

### 17. submission_list.html
Replace load: YES
Replace lines 23-30 (7-line block with commented lines):
```
                        {% collapsible_filter filter label="Filter Submissions" collapse_id="submissionFilter" %}
```

### 18. training_list.html
Replace load: YES
Replace lines 15-22 (7-line block with commented lines):
```
                        {% collapsible_filter filter label="Filter Trainings" collapse_id="trainingFilter" %}
```

## Files to SKIP (deviations from expected pattern)

1. regions/task_list.html - Has {% csrf_token %} in form block (4 lines instead of 3)
2. scores/chapterscore_list.html - Has {% csrf_token %} in form block
3. scores/score_list.html - Has {% csrf_token %} in form block
4. tasks/task_list.html - Has {% csrf_token %} in form block
5. users/user_list.html - Has {% csrf_token %} in form block
6. submissions/geararticle_list.html - Broken form block (no opening <form> tag)

