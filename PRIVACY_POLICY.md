# Privacy Policy — AutoShorts Studio

**Effective Date:** November 11, 2026

## 1. Local-First Architecture
AutoShorts Studio (`auto-shorts-android`) operates locally on your own device (Android/Termux or Desktop). The project authors do not operate any central server or collect your personal data.

## 2. Information Processed via TikTok Integration
When you authorize AutoShorts Studio via TikTok Login Kit (`user.info.basic`, `video.upload`, `video.publish`):
- OAuth2 access and refresh tokens are stored exclusively inside your local `.env` file on your own device.
- Selected `.mp4` videos and metadata (`caption`, `privacy_level`) are transmitted directly from your device to TikTok's official Content Posting API (`https://open.tiktokapis.com/`).
- No credentials, analytics, or user data are shared with or sold to third parties.

## 3. Data Retention & Deletion
- Tokens and rendered video files remain only on your local storage and are automatically pruned by the built-in storage retention manager or whenever you delete them.
- Revoking app permissions in your TikTok app settings immediately invalidates future API access.

## 4. Contact
Questions or privacy requests: https://github.com/ManoAlee/auto-shorts-android/issues
