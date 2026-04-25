"""UserFrame — the User tab for the School Tool desktop shell.

Laid out as a vertical stack of four collapsible sections:
  Account · Service · Invoices · Support

P5 modules (toolkit.account, toolkit.licence) are imported lazily
so the frame constructs cleanly even when P5 has not yet landed.
"""

from __future__ import annotations

import logging
import platform
import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as ttk
import webbrowser
from typing import TYPE_CHECKING, Any, Literal

from app_metadata import APP_VERSION, SUPPORT_EMAIL
from toolkit import tokens
from toolkit.primitives import Banner, SectionHeader

if TYPE_CHECKING:
    from toolkit.fonts import FontMap

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal font helper (duplicates the pattern in primitives to avoid
# importing FontMap at module level, which creates a circular-ish concern)
# ---------------------------------------------------------------------------


def _font(size: int, weight: Literal["normal", "bold"] = "normal") -> tkfont.Font:
    return tkfont.Font(family="Segoe UI", size=size, weight=weight)


def _mono(size: int) -> tkfont.Font:
    return tkfont.Font(family="Cascadia Mono", size=size)


# ---------------------------------------------------------------------------
# Licence state → human readable pill text
# ---------------------------------------------------------------------------

_STATE_LABELS: dict[str, str] = {
    "none": "No licence",
    "invoice_issued": "Invoice issued",
    "po_uploaded": "PO uploaded",
    "under_review": "Under review",
    "active": "Active",        # extended below with date
    "grace": "Expired",        # extended below with grace info
    "expired": "Expired",
}

_STATE_LEVEL: dict[str, str] = {
    "none": "neutral",
    "invoice_issued": "info",
    "po_uploaded": "info",
    "under_review": "warning",
    "active": "ok",
    "grace": "warning",
    "expired": "danger",
}


# ---------------------------------------------------------------------------
# Lazy loaders — return the real typed state on success, a sensible default
# instance on runtime failure (corrupt file, missing crypto, etc.). Using the
# real dataclasses (not stand-in classes) means attribute drift breaks loudly.
# ---------------------------------------------------------------------------


def _load_account_state() -> Any:
    from toolkit.account import AccountState, load_state

    try:
        return load_state()
    except Exception as exc:
        logger.warning("account.load_state failed: %s", exc)
        return AccountState(is_signed_in=False)


def _load_licence_status() -> Any:
    from toolkit.licence import LicenceStatus, read_status

    try:
        return read_status()
    except Exception as exc:
        logger.warning("licence.read_status failed: %s", exc)
        return LicenceStatus(state="none")


# ---------------------------------------------------------------------------
# UserFrame
# ---------------------------------------------------------------------------


class UserFrame(tk.Frame):
    """Top-level User tab frame.

    Parameters
    ----------
    parent:
        The Tk parent widget (the shell's content_outer frame).
    fonts:
        Shell FontMap (optional — falls back to system defaults if absent).
    """

    def __init__(
        self,
        parent: tk.Widget,
        fonts: FontMap | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(parent, bg=tokens.BG_MUTED, **kwargs)

        from toolkit.account import AccountState
        from toolkit.licence import LicenceStatus

        self._fonts = fonts
        self._account: Any = AccountState(is_signed_in=False)
        self._licence: Any = LicenceStatus(state="none")

        # Cached section sub-frames (rebuilt on refresh)
        self._account_section: tk.Frame | None = None
        self._service_section: tk.Frame | None = None
        self._invoices_section: tk.Frame | None = None
        self._support_section: tk.Frame | None = None

        # Scrollable canvas wrapper
        canvas = tk.Canvas(self, bg=tokens.BG_MUTED, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(canvas, bg=tokens.BG_MUTED)
        self._canvas_win = canvas.create_window((0, 0), window=self._inner, anchor="nw")

        def _on_inner_configure(_e: Any) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e: Any) -> None:
            canvas.itemconfigure(self._canvas_win, width=e.width)

        self._inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Top-level section header
        hdr_frame = tk.Frame(self._inner, bg=tokens.BG_MUTED)
        hdr_frame.pack(fill="x", padx=tokens.SP_4, pady=(tokens.SP_4, 0))
        SectionHeader(
            hdr_frame,
            title="User",
            subtitle="Your account, licence, invoices and support.",
        ).pack(fill="x")

        # Error banner slot (shown when P5 modules fail at runtime)
        self._error_banner_frame = tk.Frame(self._inner, bg=tokens.BG_MUTED)
        self._error_banner_frame.pack(fill="x", padx=tokens.SP_4)

        # Placeholder section containers (rebuilt by refresh())
        self._sections_frame = tk.Frame(self._inner, bg=tokens.BG_MUTED)
        self._sections_frame.pack(fill="x", padx=tokens.SP_4, pady=(tokens.SP_GAP_SECTION, 0))

        self._build_sections()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-read AccountState and LicenceStatus, then redraw all sections."""
        try:
            self._account = _load_account_state()
        except Exception as exc:
            self._show_error(f"Could not load account state: {exc}")
        try:
            self._licence = _load_licence_status()
        except Exception as exc:
            self._show_error(f"Could not load licence status: {exc}")

        self._clear_error()
        self._rebuild_sections()

    # -----------------------------------------------------------------------
    # Internal build helpers
    # -----------------------------------------------------------------------

    def _build_sections(self) -> None:
        self._rebuild_sections()

    def _rebuild_sections(self) -> None:
        # Destroy and recreate all section children
        for child in self._sections_frame.winfo_children():
            child.destroy()

        self._build_account_section()
        self._build_service_section()
        self._build_invoices_section()
        self._build_support_section()

    def _section_frame(self, title: str) -> tuple[tk.Frame, tk.Frame]:
        """Return (outer_frame, body_frame) with a small section label header."""
        outer = tk.Frame(self._sections_frame, bg=tokens.BG_MUTED)
        outer.pack(fill="x", pady=(0, tokens.SP_GAP_SECTION))

        # Small bold section heading
        lbl = tk.Label(
            outer,
            text=title,
            bg=tokens.BG_MUTED,
            fg=tokens.FG_1,
            font=_font(tokens.FS_13, "bold"),
            anchor="w",
        )
        lbl.pack(fill="x")

        # 1 px separator under heading
        sep = tk.Frame(outer, bg=tokens.BORDER_SUBTLE, height=1)
        sep.pack(fill="x", pady=(tokens.SP_1, tokens.SP_2))

        body = tk.Frame(outer, bg=tokens.BG_MUTED)
        body.pack(fill="x", padx=(tokens.SP_2, 0))

        return outer, body

    # -----------------------------------------------------------------------
    # Account section
    # -----------------------------------------------------------------------

    def _build_account_section(self) -> None:
        outer, body = self._section_frame("Account")
        self._account_section = outer

        if self._account.is_signed_in:
            self._build_signed_in_view(body)
        else:
            self._build_sign_in_view(body)

    # -- pre-auth view -------------------------------------------------------

    def _build_sign_in_view(self, parent: tk.Frame) -> None:
        """Show sign-in form with Register… expansion."""
        container = tk.Frame(parent, bg=tokens.BG_MUTED)
        container.pack(fill="x")

        # Error banner for sign-in errors
        err_frame = tk.Frame(container, bg=tokens.BG_MUTED)
        err_frame.pack(fill="x")

        # Email
        email_lbl = tk.Label(container, text="Email", bg=tokens.BG_MUTED, fg=tokens.FG_1,
                              font=_font(tokens.FS_13), anchor="w")
        email_lbl.pack(fill="x")
        email_var = tk.StringVar()
        email_entry = tk.Entry(container, textvariable=email_var, font=_font(tokens.FS_13),
                               fg=tokens.FG_1, relief="sunken", bd=1)
        email_entry.pack(fill="x", pady=(0, tokens.SP_2))

        # Password
        pw_lbl = tk.Label(container, text="Password", bg=tokens.BG_MUTED, fg=tokens.FG_1,
                           font=_font(tokens.FS_13), anchor="w")
        pw_lbl.pack(fill="x")
        pw_var = tk.StringVar()
        pw_entry = tk.Entry(container, textvariable=pw_var, show="●",
                            font=_font(tokens.FS_13), fg=tokens.FG_1, relief="sunken", bd=1)
        pw_entry.pack(fill="x", pady=(0, tokens.SP_2))

        # Buttons
        btn_row = tk.Frame(container, bg=tokens.BG_MUTED)
        btn_row.pack(fill="x", pady=(0, tokens.SP_2))

        sign_in_btn = ttk.Button(
            btn_row,
            text="Sign in",
            style="Accent.TButton",
        )
        sign_in_btn.pack(side="left", padx=(0, tokens.SP_2))

        register_btn = ttk.Button(btn_row, text="Register\u2026")
        register_btn.pack(side="left", padx=(0, tokens.SP_2))

        forgot_btn = ttk.Button(btn_row, text="Forgot password")
        forgot_btn.pack(side="left")

        # Registration form (hidden initially)
        reg_frame = tk.Frame(container, bg=tokens.BG_MUTED)
        reg_frame.pack(fill="x")
        reg_frame.pack_forget()

        confirm_frame = tk.Frame(container, bg=tokens.BG_MUTED)
        confirm_frame.pack(fill="x")
        confirm_frame.pack_forget()

        def _show_err(msg: str) -> None:
            for w in err_frame.winfo_children():
                w.destroy()
            Banner(err_frame, level="danger", text=msg).pack(fill="x",
                                                              pady=(0, tokens.SP_2))

        def _clear_err() -> None:
            for w in err_frame.winfo_children():
                w.destroy()

        def _do_sign_in() -> None:
            _clear_err()
            email = email_var.get().strip()
            password = pw_var.get()
            if not email or not password:
                _show_err("Please enter your email and password.")
                return
            try:
                from toolkit.account import login

                login(email, password)
                self.refresh()
            except Exception as exc:
                _show_err(f"Sign in failed: {exc}")

        sign_in_btn.configure(command=_do_sign_in)
        email_entry.bind("<Return>", lambda _e: _do_sign_in())
        pw_entry.bind("<Return>", lambda _e: _do_sign_in())

        def _do_forgot() -> None:
            _clear_err()
            email = email_var.get().strip()
            if not email:
                _show_err("Enter your email address above, then click Forgot password.")
                return
            try:
                from toolkit.account import request_password_reset

                request_password_reset(email)
                for w in err_frame.winfo_children():
                    w.destroy()
                Banner(err_frame, level="ok",
                       text="Password reset email sent. Check your inbox.").pack(
                    fill="x", pady=(0, tokens.SP_2))
            except Exception as exc:
                _show_err(f"Could not send reset email: {exc}")

        forgot_btn.configure(command=_do_forgot)

        # -- Registration form -----------------------------------------------

        def _toggle_register() -> None:
            if reg_frame.winfo_ismapped():
                reg_frame.pack_forget()
                confirm_frame.pack_forget()
                register_btn.configure(text="Register\u2026")
            else:
                reg_frame.pack(fill="x")
                confirm_frame.pack(fill="x")
                register_btn.configure(text="Cancel")

        register_btn.configure(command=_toggle_register)

        self._build_registration_form(reg_frame, confirm_frame, email_var, pw_var)

    def _build_registration_form(
        self,
        reg_frame: tk.Frame,
        confirm_frame: tk.Frame,
        email_var: tk.StringVar,
        pw_var: tk.StringVar,
    ) -> None:
        """Build the inline registration form inside reg_frame/confirm_frame."""
        reg_err_frame = tk.Frame(reg_frame, bg=tokens.BG_MUTED)
        reg_err_frame.pack(fill="x")

        def _reg_err(msg: str) -> None:
            for w in reg_err_frame.winfo_children():
                w.destroy()
            Banner(reg_err_frame, level="danger", text=msg).pack(fill="x",
                                                                   pady=(0, tokens.SP_2))

        def _reg_ok(msg: str) -> None:
            for w in reg_err_frame.winfo_children():
                w.destroy()
            Banner(reg_err_frame, level="ok", text=msg).pack(fill="x",
                                                              pady=(0, tokens.SP_2))

        def _lbl_entry(parent: tk.Frame, text: str,
                       var: tk.StringVar, show: str = "") -> tk.Entry:
            tk.Label(parent, text=text, bg=tokens.BG_MUTED, fg=tokens.FG_1,
                     font=_font(tokens.FS_13), anchor="w").pack(fill="x")
            entry = tk.Entry(parent, textvariable=var, show=show,
                             font=_font(tokens.FS_13), fg=tokens.FG_1,
                             relief="sunken", bd=1)
            entry.pack(fill="x", pady=(0, tokens.SP_2))
            return entry

        reg_email_var = email_var   # reuse the email from the outer form
        reg_pw_var = pw_var         # reuse password too

        confirm_pw_var = tk.StringVar()
        _lbl_entry(confirm_frame, "Confirm password", confirm_pw_var, show="●")

        first_name_var = tk.StringVar()
        _lbl_entry(reg_frame, "First name", first_name_var)

        last_name_var = tk.StringVar()
        _lbl_entry(reg_frame, "Last name", last_name_var)

        school_name_var = tk.StringVar()
        _lbl_entry(reg_frame, "School name", school_name_var)

        abn_var = tk.StringVar()
        _lbl_entry(reg_frame, "ABN", abn_var)

        create_btn = ttk.Button(
            reg_frame,
            text="Create account",
            style="Accent.TButton",
        )
        create_btn.pack(anchor="w", pady=(tokens.SP_1, tokens.SP_2))

        def _do_register() -> None:
            for w in reg_err_frame.winfo_children():
                w.destroy()
            email = reg_email_var.get().strip()
            password = reg_pw_var.get()
            confirm = confirm_pw_var.get()
            first = first_name_var.get().strip()
            last = last_name_var.get().strip()
            school = school_name_var.get().strip()
            abn = abn_var.get().strip()

            if not all([email, password, confirm, first, last, school]):
                _reg_err("All fields except ABN are required.")
                return
            if password != confirm:
                _reg_err("Passwords do not match.")
                return

            try:
                from toolkit.account import register

                register(email, password, first, last, school, abn)
                _reg_ok(
                    "Check your inbox \u2014 click the verification link, then sign back in."
                )
                create_btn.configure(state="disabled")
            except Exception as exc:
                _reg_err(f"Registration failed: {exc}")

        create_btn.configure(command=_do_register)

    # -- signed-in view ------------------------------------------------------

    def _build_signed_in_view(self, parent: tk.Frame) -> None:
        acct = self._account

        def _ro(label: str, value: str) -> None:
            tk.Label(parent, text=label, bg=tokens.BG_MUTED, fg=tokens.FG_1,
                     font=_font(tokens.FS_13), anchor="w").pack(fill="x")
            var = tk.StringVar(value=value)
            entry = tk.Entry(parent, textvariable=var, state="readonly",
                             readonlybackground=tokens.BG_READONLY,
                             font=_font(tokens.FS_13), fg=tokens.FG_1,
                             relief="sunken", bd=1)
            entry.pack(fill="x", pady=(0, tokens.SP_2))

        _ro("Email", acct.email or "")
        _ro("School name", acct.school_name or "")
        _ro("ABN", acct.school_abn or "")

        # Error banner for change-password
        err_frame = tk.Frame(parent, bg=tokens.BG_MUTED)
        err_frame.pack(fill="x")

        btn_row = tk.Frame(parent, bg=tokens.BG_MUTED)
        btn_row.pack(fill="x", pady=(tokens.SP_1, 0))

        self._change_pw_btn = ttk.Button(
            btn_row,
            text="Change password",
        )
        self._change_pw_btn.pack(side="left", padx=(0, tokens.SP_2))

        forgot_btn = ttk.Button(btn_row, text="Forgot password")
        forgot_btn.pack(side="left", padx=(0, tokens.SP_2))

        sign_out_btn = ttk.Button(btn_row, text="Sign out")
        sign_out_btn.pack(side="left")

        # Change-password inline form (hidden initially)
        cpw_frame = tk.Frame(parent, bg=tokens.BG_MUTED)
        cpw_frame.pack(fill="x")
        cpw_frame.pack_forget()

        def _show_err(msg: str) -> None:
            for w in err_frame.winfo_children():
                w.destroy()
            Banner(err_frame, level="danger", text=msg).pack(fill="x",
                                                              pady=(0, tokens.SP_2))

        def _show_ok(msg: str) -> None:
            for w in err_frame.winfo_children():
                w.destroy()
            Banner(err_frame, level="ok", text=msg).pack(fill="x",
                                                          pady=(0, tokens.SP_2))

        def _toggle_change_pw() -> None:
            if cpw_frame.winfo_ismapped():
                cpw_frame.pack_forget()
                self._change_pw_btn.configure(text="Change password")
            else:
                cpw_frame.pack(fill="x")
                self._change_pw_btn.configure(text="Cancel")

        self._change_pw_btn.configure(command=_toggle_change_pw)

        # Change-password form
        old_pw_var = tk.StringVar()
        new_pw_var = tk.StringVar()
        confirm_new_pw_var = tk.StringVar()

        for lbl_text, var in [("Current password", old_pw_var),
                               ("New password", new_pw_var),
                               ("Confirm new password", confirm_new_pw_var)]:
            tk.Label(cpw_frame, text=lbl_text, bg=tokens.BG_MUTED, fg=tokens.FG_1,
                     font=_font(tokens.FS_13), anchor="w").pack(fill="x")
            tk.Entry(cpw_frame, textvariable=var, show="●",
                     font=_font(tokens.FS_13), fg=tokens.FG_1,
                     relief="sunken", bd=1).pack(fill="x", pady=(0, tokens.SP_2))

        save_btn = ttk.Button(cpw_frame, text="Save password", style="Accent.TButton")
        save_btn.pack(anchor="w", pady=(tokens.SP_1, tokens.SP_2))

        def _do_change_pw() -> None:
            for w in err_frame.winfo_children():
                w.destroy()
            old = old_pw_var.get()
            new = new_pw_var.get()
            confirm = confirm_new_pw_var.get()
            if not old or not new or not confirm:
                _show_err("All three password fields are required.")
                return
            if new != confirm:
                _show_err("New passwords do not match.")
                return
            try:
                from toolkit.account import change_password

                change_password(old, new)
                _show_ok("Password changed successfully.")
                cpw_frame.pack_forget()
                self._change_pw_btn.configure(text="Change password")
            except Exception as exc:
                _show_err(f"Could not change password: {exc}")

        save_btn.configure(command=_do_change_pw)

        # Forgot password
        def _do_forgot() -> None:
            for w in err_frame.winfo_children():
                w.destroy()
            email = acct.email or ""
            if not email:
                _show_err("No email address on record.")
                return
            try:
                from toolkit.account import request_password_reset

                request_password_reset(email)
                _show_ok("Password reset email sent. Check your inbox.")
            except Exception as exc:
                _show_err(f"Could not send reset email: {exc}")

        forgot_btn.configure(command=_do_forgot)

        # Sign out
        def _do_sign_out() -> None:
            try:
                from toolkit.account import logout

                logout()
            except Exception as exc:
                logger.warning("logout failed: %s", exc)
            self.refresh()

        sign_out_btn.configure(command=_do_sign_out)

    # -----------------------------------------------------------------------
    # Service section
    # -----------------------------------------------------------------------

    def _build_service_section(self) -> None:
        outer, body = self._section_frame("Service")
        self._service_section = outer

        lic = self._licence

        # Status pill
        pill_text, pill_level = self._licence_pill(lic)
        pill_row = tk.Frame(body, bg=tokens.BG_MUTED)
        pill_row.pack(fill="x", pady=(0, tokens.SP_2))
        tk.Label(pill_row, text="Status:", bg=tokens.BG_MUTED, fg=tokens.FG_1,
                 font=_font(tokens.FS_13), anchor="w").pack(side="left",
                                                             padx=(0, tokens.SP_2))

        pill_styles = {
            "ok":      {"bg": tokens.OK_BG,     "fg": tokens.OK_FG},
            "warning": {"bg": tokens.WARN_BG,   "fg": tokens.WARN_FG},
            "danger":  {"bg": tokens.DANGER_BG, "fg": tokens.DANGER_FG},
            "info":    {"bg": tokens.INFO_BG,   "fg": tokens.INFO_FG},
            "neutral": {"bg": tokens.BG_INSET,  "fg": tokens.FG_2},
        }
        ps = pill_styles.get(pill_level, pill_styles["neutral"])
        self._status_pill_lbl = tk.Label(
            pill_row,
            text=pill_text,
            bg=ps["bg"],
            fg=ps["fg"],
            font=_font(tokens.FS_13),
            padx=tokens.SP_2,
            pady=2,
            relief="flat",
        )
        self._status_pill_lbl.pack(side="left")

        # Bound devices list
        tk.Label(body, text="Devices:", bg=tokens.BG_MUTED, fg=tokens.FG_1,
                 font=_font(tokens.FS_13, "bold"), anchor="w").pack(
            fill="x", pady=(tokens.SP_2, tokens.SP_1))

        devices: list[str] = list(lic.devices) if lic.devices else []
        if devices:
            for dev in devices:
                tk.Label(body, text=f"\u2022  {dev}", bg=tokens.BG_MUTED, fg=tokens.FG_2,
                         font=_font(tokens.FS_13), anchor="w").pack(fill="x")
        else:
            tk.Label(body, text="No devices registered.", bg=tokens.BG_MUTED,
                     fg=tokens.FG_MUTED, font=_font(tokens.FS_13), anchor="w").pack(fill="x")

        # Action buttons (M2 stubs)
        btn_row = tk.Frame(body, bg=tokens.BG_MUTED)
        btn_row.pack(fill="x", pady=(tokens.SP_2, 0))

        stub_banner_frame = tk.Frame(body, bg=tokens.BG_MUTED)
        stub_banner_frame.pack(fill="x")

        def _coming_m4(action: str) -> None:
            for w in stub_banner_frame.winfo_children():
                w.destroy()
            Banner(stub_banner_frame, level="info",
                   text=f"{action} \u2014 coming in M4.").pack(
                fill="x", pady=(tokens.SP_1, 0))

        state = lic.state

        if state in ("none", "invoice_issued"):
            ttk.Button(
                btn_row, text="Generate annual invoice",
                command=lambda: _coming_m4("Generate annual invoice"),
            ).pack(side="left", padx=(0, tokens.SP_2))

        if state == "invoice_issued":
            ttk.Button(
                btn_row, text="Download invoice",
                command=lambda: _coming_m4("Download invoice"),
            ).pack(side="left", padx=(0, tokens.SP_2))

        if state in ("invoice_issued", "po_uploaded", "under_review"):
            ttk.Button(
                btn_row, text="Upload signed PO",
                command=lambda: _coming_m4("Upload signed PO"),
            ).pack(side="left", padx=(0, tokens.SP_2))

        ttk.Button(
            btn_row, text="Refresh licence",
            command=self._do_refresh_licence,
        ).pack(side="left", padx=(0, tokens.SP_2))

        if state == "active":
            ttk.Button(
                btn_row, text="Renew licence",
                command=lambda: _coming_m4("Renew licence"),
            ).pack(side="left")

    def _licence_pill(self, lic: Any) -> tuple[str, str]:
        """Return (display text, banner level) for the licence status pill."""
        state: str = getattr(lic, "state", "none")
        expires_at = getattr(lic, "expires_at", None)

        if state == "active" and expires_at is not None:
            try:
                date_str = expires_at.strftime("%Y-%m-%d")
                return f"Active until {date_str}", "ok"
            except Exception:
                return "Active", "ok"

        if state == "grace" and expires_at is not None:
            try:
                import datetime

                now = datetime.datetime.now(tz=expires_at.tzinfo)
                grace_end = expires_at + datetime.timedelta(days=14)
                days_left = max(0, (grace_end - now).days)
                return f"Expired (grace period ends in {days_left} day(s))", "warning"
            except Exception:
                return "Expired (grace period)", "warning"

        label = _STATE_LABELS.get(state, state.replace("_", " ").capitalize())
        level = _STATE_LEVEL.get(state, "neutral")
        return label, level

    def _do_refresh_licence(self) -> None:
        try:
            from toolkit.licence import refresh

            self._licence = refresh()
            self.refresh()
        except Exception as exc:
            logger.warning("licence.refresh failed: %s", exc)
            # Surface error in sections
            self._show_error(f"Licence refresh failed: {exc}")

    # -----------------------------------------------------------------------
    # Invoices section
    # -----------------------------------------------------------------------

    def _build_invoices_section(self) -> None:
        outer, body = self._section_frame("Invoices")
        self._invoices_section = outer

        columns = [
            {"key": "number",    "label": "Number",         "width": 120},
            {"key": "issue_date","label": "Issue date",     "width": 90},
            {"key": "period",    "label": "Period",         "width": 150},
            {"key": "total",     "label": "Total inc GST",  "width": 100, "align": "right",
             "mono": True},
            {"key": "status",    "label": "Status",         "width": 80},
            {"key": "download",  "label": "Download",       "width": 80},
        ]

        col_ids = [str(c["key"]) for c in columns]
        tree = ttk.Treeview(body, columns=col_ids, show="headings", height=5)
        for col in columns:
            cid = str(col["key"])
            raw_w = col.get("width", 100)
            col_w = int(raw_w) if isinstance(raw_w, (int, float)) else 100
            is_right = col.get("align") == "right" or bool(col.get("mono"))
            col_anchor: Literal["e", "w"] = "e" if is_right else "w"
            tree.heading(cid, text=str(col["label"]))
            tree.column(cid, width=col_w, anchor=col_anchor, stretch=True)

        vsb = ttk.Scrollbar(body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        # M2: empty state label below table
        empty_lbl = tk.Label(
            outer,
            text="No invoices yet.",
            bg=tokens.BG_MUTED,
            fg=tokens.FG_MUTED,
            font=_font(tokens.FS_13),
            anchor="w",
        )
        empty_lbl.pack(fill="x", padx=(tokens.SP_2, 0), pady=(tokens.SP_1, 0))

    # -----------------------------------------------------------------------
    # Support section
    # -----------------------------------------------------------------------

    def _build_support_section(self) -> None:
        outer, body = self._section_frame("Support")
        self._support_section = outer

        mailto_btn = ttk.Button(
            body,
            text="Email support",
            style="Accent.TButton",
            command=self._open_support_email,
        )
        mailto_btn.pack(anchor="w", pady=(0, tokens.SP_2))

        feedback_lbl = tk.Label(
            body,
            text=f"Feedback welcome \u2014 {SUPPORT_EMAIL}",
            bg=tokens.BG_MUTED,
            fg=tokens.FG_MUTED,
            font=_font(tokens.FS_13),
            anchor="w",
        )
        feedback_lbl.pack(fill="x")

    def _open_support_email(self) -> None:
        email = getattr(self._account, "email", None) or "Not signed in"
        lic_state = getattr(self._licence, "state", "unknown")
        os_info = platform.platform()

        body_lines = [
            f"App version: {APP_VERSION}",
            f"OS: {os_info}",
            f"User email: {email}",
            f"Licence status: {lic_state}",
            "",
            "Please describe your issue:",
            "",
        ]
        import urllib.parse

        body_str = urllib.parse.quote("\n".join(body_lines))
        subject = urllib.parse.quote("School Tool support")
        mailto_url = f"mailto:{SUPPORT_EMAIL}?subject={subject}&body={body_str}"
        try:
            webbrowser.open(mailto_url)
        except Exception as exc:
            logger.warning("Could not open mailto: %s", exc)

    # -----------------------------------------------------------------------
    # Error banner helpers
    # -----------------------------------------------------------------------

    def _show_error(self, message: str) -> None:
        for w in self._error_banner_frame.winfo_children():
            w.destroy()
        Banner(self._error_banner_frame, level="danger", text=message).pack(
            fill="x", pady=(0, tokens.SP_2))

    def _clear_error(self) -> None:
        for w in self._error_banner_frame.winfo_children():
            w.destroy()
