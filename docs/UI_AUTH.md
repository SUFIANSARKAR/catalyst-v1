# Catalyst UI & identity

Catalyst now presents two responsive product interfaces from one codebase:
- Desktop: three-pane command cockpit with navigation, live activity, command center, and full controls.
- Android/mobile: touch-first single-pane chat with bottom navigation, compact controls, installable PWA shell, microphone and creation shortcuts.

## Google sign-in
Set `CATALYST_GOOGLE_CLIENT_ID`, `CATALYST_GOOGLE_CLIENT_SECRET`, and optionally `CATALYST_GOOGLE_REDIRECT_URI`. Google OAuth uses authorization-code flow and Google userinfo; no Google password is handled by Catalyst.

## Creator Admin
The Admin button opens a separate Creator unlock. The configured Creator password is verified by SHA-256 comparison and never stored in plaintext. Successful unlock creates an HttpOnly session cookie and grants the creator policy role.

The shipped default Creator password is the user-requested value; the source stores only its SHA-256 digest. For production deployments, replace this bootstrap credential with an environment-managed secret and rotate it.
