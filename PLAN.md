# Face Recognition Login Interface Plan

## Summary
Design a polished responsive web login interface with two clear sign-in modes: **Face Recognition** and **Email + Password**. The experience should feel premium, calm, and human-designed, avoiding generic AI-style visuals, heavy gradients, glowing effects, or overly rounded “template” cards.

Use **WebAuthn platform biometrics** for real face login where available, such as Windows Hello, Face ID, or compatible device authenticators. The app should not perform raw camera-based facial recognition in the browser.

## Key Changes
- Build a centered authentication screen with a restrained visual style: soft neutral background, sharp typography, subtle borders, realistic spacing, and no radiant/gradient-heavy treatment.
- Add a segmented login method switch:
  - `Face Recognition`
  - `Email`
- Face mode:
  - Primary action: `Continue with face recognition`
  - Show device support status.
  - Use WebAuthn/passkey authentication through the platform authenticator.
  - Provide fallback link: `Use email instead`.
- Email mode:
  - Email input
  - Password input
  - Show/hide password icon button
  - Submit button
  - Forgot password link
  - Optional return link: `Use face recognition`
- Add clear states:
  - Idle
  - Checking device support
  - Awaiting biometric prompt
  - Success
  - Failed / canceled
  - Unsupported device fallback
- Keep copy short, direct, and trustworthy.

## Interface/API Assumptions
- Frontend target: responsive web app.
- Real biometric login uses WebAuthn/passkeys, not custom camera face matching.
- Required auth functions:
  - `checkBiometricSupport()`
  - `startBiometricLogin()`
  - `loginWithEmailPassword(email, password)`
- Backend must provide WebAuthn challenge generation and verification endpoints.
- Email/password remains available at all times as the reliable fallback.

## UX And Visual Direction
- Layout: compact login panel beside or above a quiet brand area depending on viewport.
- Desktop: two-column composition with the form as the main interactive surface.
- Mobile: single-column, form-first layout.
- Avoid:
  - Purple/blue radiant backgrounds
  - Glowing orbs
  - AI-face illustrations
  - Overly futuristic scan-line effects
  - Decorative camera previews unless actual camera use is required
- Prefer:
  - Clean neutral palette
  - One confident accent color
  - Thin borders
  - Strong focus states
  - Professional iconography for face, mail, lock, eye, and alert states

## Test Plan
- Verify switching between face and email modes preserves expected form state.
- Verify unsupported biometric devices default gracefully to email login.
- Verify canceled biometric prompts show a useful retry/fallback message.
- Verify keyboard navigation, focus rings, labels, and screen-reader announcements.
- Test responsive layout at mobile, tablet, and desktop widths.
- Test error states for invalid email/password, network failure, and biometric verification failure.

## Assumptions
- The interface is for a web application.
- “Face recognition” means secure platform biometric authentication through WebAuthn.
- The design should feel modern and premium, but understated rather than futuristic.
- No implementation files currently exist in the workspace, so this plan is stack-neutral but ready to implement in React, Next.js, Vue, or similar frontend frameworks.
