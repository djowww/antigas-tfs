# tibia74.tech security review — 2026-09-28

Scope: public pages and downloads, local PHP source, the private web security helper (reviewed without disclosing configuration values), and the live Nginx/Cloudflare response path. Testing used non-mutating GET/HEAD requests and configuration/code inspection only; no account, payment, or game data was changed.

## Applied

- Added one-year HSTS on the HTTPS virtual host. The policy omits includeSubDomains and preload until every subdomain has been validated.
- Added CSP, nosniff, frame protection, referrer, and permissions headers to static files and legacy-download redirects. PHP pages already set these headers through the private application library.
- Configured Nginx to trust CF-Connecting-IP only when the TCP peer is in Cloudflare's published IPv4/IPv6 networks. Direct-origin requests keep their socket IP, so the existing per-IP registration, login, and Pix limits distinguish visitors.
- Restricted inbound ports 80 and 443 to Cloudflare's published networks, closing direct-origin access. SSH and game ports are unchanged.
- Disabled Nginx version disclosure.
- Versioned the language/wiki CSS and client-download links so visitors get the new headers instead of old Cloudflare-cached objects.

## Verified existing controls

- HTTP redirects to HTTPS; live TLS responses set Secure, HttpOnly, and SameSite=Lax session cookies.
- Session strict mode and cookie-only mode, 30-minute idle expiry, random 256-bit CSRF tokens, session ID rotation at login/password change, prepared database statements, input validation, and server-side account/object checks are present.
- The web database connection is restricted to the intended database names; MariaDB listens on loopback. No public upload route or user-controlled file execution path was found.
- The installed PHP package is Ubuntu's 8.1.2-1ubuntu2.26 security-maintained package, not an unpatched upstream 8.1.2 build. Continued patching depends on Ubuntu security updates.

## Residual work

- Passwords use SHA-1 because the existing game server uses that credential format. A site-only change would break game logins; migration requires coordinated game-server support and a safe rehash strategy.
- PHP 8.1 reached upstream end of life on 2025-12-31. The host has Ubuntu's updated Jammy package at this audit date; schedule a compatibility-tested move to an upstream-supported branch rather than changing runtime versions during this hardening.
- There is no email-based account recovery or MFA. Adding either requires a verified recovery channel or compatible game-server changes.
- Cloudflare IP ranges are pinned in Nginx and UFW. Review them periodically and update before Cloudflare changes its list: https://www.cloudflare.com/ips-v4 and https://www.cloudflare.com/ips-v6.
- The account-wide login throttle limits repeated guesses, but a distributed attacker can temporarily make a targeted account hit its threshold. Revisit this trade-off if recovery or MFA is introduced.

## Validation

- Nginx configuration test passed and Nginx reloaded successfully. Four changed PHP pages passed php -l before and after publication.
- Public home, account, coins, and wiki pages returned HTTP 200 with HSTS, CSP, nosniff, frame protection, referrer/permissions policy, and Secure/HttpOnly/SameSite=Lax cookies.
- Versioned CSS, SVG, and client ZIP responses returned HTTP 200 with HSTS and static-resource security headers. A retired-client URL returned the expected HTTP 302 with those headers. HTTP redirects permanently to HTTPS.
- Requests for /.env, /.git/config, config.lua, the private helper, the CLI Pix approval script, and a backup SQL path returned HTTP 404.
- UFW verified Cloudflare IPv4 and IPv6 allow rules before removing the open 80/443 rules. The public site then returned HTTP 200 through Cloudflare, and a direct-origin HTTPS connection from outside Cloudflare was blocked.
- No POST login, registration, character creation, password change, or payment action was submitted.

Standards references: OWASP HTTP Security Response Headers and Session Management Cheat Sheets; Cloudflare's official IP-address documentation; PHP/Ubuntu package support as observed on the host.
