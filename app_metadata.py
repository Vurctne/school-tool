from __future__ import annotations

APP_NAME = "School Tool"
APP_VERSION = "2.0.0"
APP_AUTHOR = "Vurctne"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"
SUPPORT_EMAIL = "Vurctne@gmail.com"
APP_SLUG = "school-tool"
APP_INSTALLER_ID = "{f07881a0-d07c-45ae-bf32-c5ce54c87220}"
# Backend URL. After schooltool.com.au is live in Cloudflare
# (see docs/05_DOMAIN_SETUP.md), flip this to "https://api.schooltool.com.au".
API_BASE_URL = "https://sft-api.mfiking.workers.dev"
# Ed25519 public key for licence verification (server keypair populated in M2).
LICENCE_PUBLIC_KEY = b"wcRc4HvZF4C1jwvB6X7QHenidUlo6XQIPro4wLuMp7A="
