from __future__ import annotations

APP_NAME = "School Tool"
# Version format: MAJOR.MINOR.BUILD.REVISION (4-part, MSIX-compatible).
# BUILD auto-increments on every build via scripts/bump_version.py
# (called from msix/build_msix_package.ps1 unless -NoVersionBump is set).
# REVISION must stay at 0 — Microsoft Store rejects MSIX submissions with
# REVISION != 0. Bump MAJOR/MINOR manually; reset BUILD/REVISION to 0/0
# when you do.
APP_VERSION = "2.4.15.0"
APP_AUTHOR = "Vurctne"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"
SUPPORT_EMAIL = "feedback@schooltool.com.au"
# Round 42 — second mailbox for non-feedback queries (account help,
# bug reports needing back-and-forth, partnership / Store / press
# enquiries, anything that needs an actual human reply). This inbox
# is human-monitored; SUPPORT_EMAIL (feedback@) is AI-monitored and
# gets a weekly digest, not a per-message reply.
CONTACT_EMAIL = "contact@schooltool.com.au"
APP_SLUG = "school-tool"
APP_INSTALLER_ID = "{f07881a0-d07c-45ae-bf32-c5ce54c87220}"
# Microsoft Store identity (Round 16). See docs/store_publish.md.
STORE_PACKAGE_IDENTITY_NAME = "Vurctne.VicSchoolFinanceTools"
STORE_PUBLISHER = "CN=E75204F6-F77B-4E0C-89C6-AC00A663F6A0"
STORE_PUBLISHER_DISPLAY_NAME = "Vurctne"
# Backend URL. After schooltool.com.au is live in Cloudflare
# (see docs/05_DOMAIN_SETUP.md), flip this to "https://api.schooltool.com.au".
API_BASE_URL = "https://sft-api.mfiking.workers.dev"
# Ed25519 public key for licence verification (server keypair populated in M2).
LICENCE_PUBLIC_KEY = b"wcRc4HvZF4C1jwvB6X7QHenidUlo6XQIPro4wLuMp7A="
# Show the User tab in the left rail. Currently False — the User tab
# (account / service / invoices) is not shown to end users.
SHOW_USER_TAB: bool = False
