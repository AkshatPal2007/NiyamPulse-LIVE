# Real-account setup and operating guide

This is the real-account application, not the old persona demo. The native local
build is complete; email delivery, your administrator identity and public-host
configuration are operator inputs. No production users or passwords are invented.

## What is already prepared

- React public home, exam catalog, reviewed-source feed, sign-in, verified email
  account setup, password reset, account preferences and role-protected operations.
- Passwords use Argon2id; opaque sessions use HttpOnly cookies. Tokens are hashed
  at rest, role assignment is server-controlled, and account writes check CSRF/origin.
- The active database is `var/production/niyampulse.sqlite3`: 13 genuine discoveries,
  one previously human-reviewed UPSC update, no demo users/subscriptions/inbox rows.
- Genuine evidence, extraction/model caches and the entire Sarvam ledger are
  preserved. Ten admitted operations reserve the full prior ₹50 cap; paid requests
  remain paused. The 500-credit floor and expiring manual balance snapshot remain.
- The pre-cutover database is backed up under `var/backups/`. The original
  `var/niyampulse.sqlite3` is historical; it is no longer the default runtime path.

## 1. Configure email privately

### Current setup: Gmail SMTP

The owner email has been supplied. Gmail connection settings and that sender
identity are prepared only in the ignored local `.env`; no private email address
or credential belongs in this tracked guide. The credential has now been supplied
privately and SMTP TLS/authentication succeeded. The existing verified owner account
was promoted and the user confirmed admin access; no new invitation was sent.
The following steps remain the reference for future SMTP reconfiguration.

1. Sign in to the intended Gmail account and enable 2-Step Verification in
   [Google Account security](https://myaccount.google.com/security), if needed.
2. Open [App passwords](https://myaccount.google.com/apppasswords), create one
   named `NiyamPulse`, and copy it privately. Google requires 2-Step Verification
   for app passwords; account policies can make this option unavailable. See
   [Google's instructions](https://support.google.com/accounts/answer/185833?hl=en).
3. In the local `.env`, set `SMTP_PASSWORD` to the generated app password without
   Google's display spaces. Do not use the normal Google login password, paste
   any credential into chat, or commit it. Keep the existing Sarvam key unchanged.
4. Run the status command below. After the credential is present, continue with
   the server restart and administrator invitation in sections 2 and 3.

```powershell
.\.venv\Scripts\python.exe -m backend.accounts status
```

The prepared connection uses `smtp.gmail.com`, port `587`, and STARTTLS, as in
[Google's SMTP documentation](https://developers.google.com/workspace/gmail/imap/imap-smtp).
An authenticated connection needs both username and password; incomplete pairs
keep registration and recovery disabled. A configured flag only confirms local
settings, not successful authentication or email delivery. The invitation's SMTP
acceptance followed by your actual inbox/link check supplies that evidence.

The NiyamPulse account password is a separate password chosen through the invitation
link. If App passwords is unavailable, report the message; do not disable existing
Google security protections to work around it. Gmail is the initial low-volume
setup; the sender/delivery plan for a public launch remains an operator decision.

### Other SMTP providers

The existing `.env` retains your Sarvam key. Add real values for:

```dotenv
SMTP_HOST=your_provider_smtp_hostname
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password_or_app_password
SMTP_FROM=your_verified_sender_email
```

For implicit TLS, use the provider's port (commonly 465) and `SMTP_SECURITY=ssl`.
Use the settings from your provider; placeholders do not constitute a connection.
Keep passwords/API keys in `.env`, never in chat, frontend code or Git. Without
configured mail, registration/recovery are explicitly unavailable; public browsing
still works. No test mailbox, pretend sent email or default password is substituted.

Email links point to `NIYAMPULSE_PUBLIC_URL`. For native local use, this is
`http://127.0.0.1:8000`; open the link on the same machine. Provider acceptance and
final inbox delivery are different; only an actual inbox check verifies delivery.

## 2. Start the current application

Stop any previous server in its own terminal with Ctrl+C, then run:

```powershell
.\.venv\Scripts\python.exe -m backend.serve
```

Open http://127.0.0.1:8000/. After completing the invitation below, sign in with
your verified account. Administrator
access follows the stored role; there is no persona switch or impersonation.
Ordinary users register using their own mailbox and choose exam cycles after
verification. A new subscription also receives up to twenty reviewed informational
updates from the last thirty days; rule amendments are not replayed as personal
before/after assessments. All future alerts still require a human source review.

Source polling and extraction run on the backend independently of the browser.
Run one stack: this API, or the standalone `python -m backend.monitor`, not both.
Budget-paused jobs remain visible and do not spend additional credits.

## 3. Invite your actual administrator

Keep the updated server running. Open a second PowerShell terminal at the
repository root:

```powershell
.\.venv\Scripts\python.exe -m backend.accounts status
.\.venv\Scripts\python.exe -m backend.accounts invite-admin
```

Enter the real owner email at the prompt and confirm an adult account holder.
The command sends a single-use invitation through the configured provider. Open
that email, then choose your own password in the app (15–128 characters). Nothing
prints or transmits your password through chat. Tokens expire after 24 hours.

For an existing verified learner that you explicitly want to promote:

```powershell
.\.venv\Scripts\python.exe -m backend.accounts promote-admin
```

This requires local console access and an explicit PROMOTE confirmation, revokes
existing sessions, and records the role change. Public signup cannot set roles.

## 4. Before an Internet-facing release

Set `NIYAMPULSE_ENV=production` and replace `NIYAMPULSE_PUBLIC_URL` with your actual
canonical HTTPS origin. Production refuses plain HTTP and demo identities. Use
one Windows API process behind your HTTPS endpoint; configure trusted proxy/host
settings and protect the SQLite database, `.env`, and backups from public access.
The current work does not provision hosting, a domain or certificates. Follow
[the deployment guide](DEPLOYMENT.md) for the durable-storage declaration, absolute
data path, runtime checks and private backup/restore cutover.

Initial registration supports adult holders/guardians and collects no child DOB.
The adult checkbox is a self-declaration, not verified age/parental consent.
Direct child accounts need a separately reviewed consent workflow. Account security
and deployment policies should be reviewed before accepting public candidate data;
this implementation is not a claim of legal compliance or a completed security audit.

## Validation and limits

Native Windows Python 3.12 tests cover real-account boundaries, resets, expiry,
CSRF/origin checks, cookie flags, role enforcement, deletion, rate limits, password
races and data migration. Local SMTP authentication and real administrator access
are now verified; hosted SMTP/link delivery and learner/restart acceptance still
require the chosen host. No real credentials are used in automated tests.

Primary security references: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/api.html).

## Administrator role missing on a deployed Render service

Roles live in that service's SQLite database, not frontend/browser storage or Git.
The owner's local account was verified as ADMIN; this does not promote a separately
registered account in a fresh Render database. Never commit/copy the live SQLite
file into a public repository or add an email-based role bypass.

Open the running backend service's Render Shell (not a build/pre-deploy command
or isolated ephemeral instance). Verify the configured existing data file first:

```sh
python -c "import os; from pathlib import Path; p=Path(os.environ['NIYAMPULSE_DATA_DIR'])/'niyampulse.sqlite3'; print(p); print('Database exists:',p.is_file())"
python -m backend.accounts promote-admin --email akshatpc12345@gmail.com
```

Type PROMOTE when prompted. This requires an existing verified real account,
changes its stored server-side role and revokes its sessions. Sign in again after
promotion. If VERIFIED_ACCOUNT_REQUIRED appears, register/verify the mailbox on
the deployed app first, then rerun. Do not bypass mailbox verification.

NIYAMPULSE_DATA_DIR must refer to the application's existing data directory beneath
the attached disk mount (including any restored subdirectory), not a different
fresh directory. Only disk-backed paths survive Render redeploys. Do not change
paths or overwrite the live database simply to assign a role.
