# Round 34 — Switch support email + trim privacy policy

**Date:** 2026-05-02

---

## User asks

1. "把所有 support Email 改为 feedback@schooltool.com.au"
   (replace all user-facing support emails with the new address)
2. Privacy policy 里面 — for example, if a future paid tier is
   reintroduced 这段话去掉
   (remove the "for example, if a future paid tier is reintroduced"
   clause from the privacy policy)

---

## Files touched (user-facing surfaces only)

```
MOD   app_metadata.py                      Vurctne@gmail.com → feedback@schooltool.com.au
MOD   toolkit/shell.py                     About panel SUPPORT line
MOD   toolkit/user_errors.py               Generic-fallback advice line
MOD   tools/hyia/frame.py                  Help-text SUPPORT block
MOD   tools/master_budget/frame.py         Help-text SUPPORT block (×2 occurrences)
MOD   tools/sub_program/frame.py           Help-text SUPPORT block (×2 occurrences)
MOD   tools/operating/frame.py             Help-text SUPPORT block
MOD   tools/srp/frame.py                   Help-text SUPPORT block (×2 occurrences)
MOD   tools/refined_pal_search/frame.py    Help-text SUPPORT block (×2 occurrences)

MOD   docs/store_privacy_policy.md         Last-updated bumped to 2026-05-02;
                                           Contact + bottom contact line updated;
                                           "for example, if a future paid tier is
                                           reintroduced…" passage removed.
MOD   docs/store_listing_copy.md           SUPPORT block + Partner Center "Support
                                           contact info" reference table.

MOD   tests/test_user_errors.py            test_unknown_exception_uses_fallback now
                                           asserts "feedback@schooltool.com.au" in
                                           the advice (was "vurctne@gmail.com").
```

The shell.py change propagates everywhere the About / Privacy panels render — they read from `app_metadata.SUPPORT_EMAIL`, which is now the new address. Same for the in-app status bar (`v{APP_VERSION} · {SUPPORT_EMAIL}`).

---

## Files deliberately NOT touched

These all still contain the old gmail address; they are not user-facing for end users of the published app:

| File / area | Why |
| --- | --- |
| `pyproject.toml` | Package author identity baked into the wheel metadata (PyPI / project header). Not a user-visible support contact. |
| `backend/wrangler.toml`, `backend/wrangler.test.toml`, `backend/src/lib/mailer.ts`, `backend/tests/mailer.test.ts`, `backend/src/lib/env.ts` | Resend mailer FROM address. Separate concern — Task #7 tracks "Fix mailer FROM address (Resend won't sign for gmail.com)". When that task lands, the mailer will use a `noreply@schooltool.com.au` (or similar) sender on a verified Resend domain, which is independent of the user-facing support email. |
| `handoff/*.md` | Historical record. Past handoffs are frozen — they document what was true at the time, not what's true now. |
| `docs/01_REQUIREMENTS.md`, `docs/02–05_*.md`, `docs/Tools_in_Development.md`, `docs/03_ROADMAP.md`, `docs/04_BACKEND_DESIGN.md` | Internal design docs and ADR references. Not shipped to end users. |
| `CLAUDE.md`, `README.md`, `TESTING.md`, `CONTEXT-SUMMARY.md`, `PROJECT-INVENTORY.md` | Project-level metadata for developers (and you). Not user-facing. |

If you want any of these also updated, say so — the swap is two minutes per file.

---

## Privacy policy diff

**Before** (lines 82–86):

```
If our practices change in the future — for example, if a future paid tier is reintroduced
that requires server-side licence verification — this policy will be updated and the
previous version will remain accessible in the project's source control history. Material
changes will be reflected in a new "Last updated" date at the top of this page and noted
in the app's Store listing description.
```

**After**:

```
If our practices change in the future, this policy will be updated and the
previous version will remain accessible in the project's source control history. Material
changes will be reflected in a new "Last updated" date at the top of this page and noted
in the app's Store listing description.
```

Plus header bumped: `**Last updated:** 2026-05-02`. The contact lines (top + bottom) now read `feedback@schooltool.com.au`.

---

## Quality gates

```
ruff format --check .   → 79 files already formatted
ruff check .             → All checks passed!
mypy --strict --cache-dir=/tmp/mypy_cache toolkit/ tools/ tests/
                         → no issues found in 72 source files
pytest --ignore=tools/operating/tests/test_logic.py
                         → 550 passed, 66 skipped (env), 1 warning
```

The `test_unknown_exception_uses_fallback` test was updated to assert
the new address, so it stays green.

---

## What this rolls into

The Store-published v2.2.1.0 still shows the old gmail.com everywhere
(About panel, error advice, every tool's Help text, the Store-hosted
privacy policy). The next .msixupload (Round 32's hotfix → v2.2.2.0
or whatever the auto-bump produces) will carry the new email through.

Recommended bundling: **ship the Round 32 _render_result fix + Round 34
email-and-privacy-policy update in the same hotfix**. They're logically
unrelated but the user impact is the same — your Store users won't see
either change until the next submission, so combining them saves a
review cycle.

For the Store listing on Partner Center, after the upload:

* Update the **Support contact info** field to `feedback@schooltool.com.au`.
* Re-paste the body of `docs/store_privacy_policy.md` into the
  Privacy Policy URL target (or update whichever GitHub Pages /
  static host you point the Privacy Policy URL at). The Store
  listing's *URL* doesn't change; only the *content* at that URL.

---

## Email setup reminder

You'll need `feedback@schooltool.com.au` to actually receive mail.
Options:

* **Forward to Vurctne@gmail.com** at the DNS / mailbox provider
  level — quickest. Users send to feedback@schooltool.com.au; you
  read it in the same Gmail inbox you already check.
* **Real mailbox** at schooltool.com.au — costs a few dollars a
  month per address through Microsoft 365 / Google Workspace / Zoho.
  Better long-term if you ever want to give a co-founder access or
  separate inbox rules.

Either works for the Store listing — the Store only validates that
the address is contactable.
