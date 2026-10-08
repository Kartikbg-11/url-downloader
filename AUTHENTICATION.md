# Three-user login

The application has three local accounts. Every download API endpoint requires login, and each user can list, view, cancel, delete, stream, or retrieve only their own downloads.

## Default development accounts

| Username | Password |
| --- | --- |
| `user1` | `User1@123` |
| `user2` | `User2@123` |
| `user3` | `User3@123` |

These credentials are for local testing only.

## Change the accounts

Copy `mini-services/url-downloader-backend/.env.example` to `.env` in the same directory. Change `AUTH_USERS` while keeping exactly three unique `username:password` pairs:

```env
AUTH_USERS=alice:strong-password-1,bob:strong-password-2,carol:strong-password-3
AUTH_SESSION_HOURS=8
AUTH_COOKIE_SECURE=false
```

Passwords may contain colons because only the first colon separates the username and password. Usernames may not contain colons or commas.

Set `AUTH_COOKIE_SECURE=true` when the application is served over HTTPS.

## Run locally

Start the backend:

```powershell
cd mini-services/url-downloader-backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

In a second terminal, start the frontend:

```powershell
npm install
npm run dev
```

Open `http://localhost:3000` and sign in.

## Test with Postman

Import either collection from the `postman` directory. The collections now start with a Login request and automatically reuse the session cookie. To test a different user, edit the `username` and `password` collection variables.

## Security behavior

- The browser receives an opaque `HttpOnly`, `SameSite=Lax` session cookie.
- Session tokens are generated with a cryptographically secure random generator.
- Login errors do not reveal whether a username exists.
- Sessions and download metadata are in memory. Restarting the backend signs everyone out and clears the visible history.
- Health, documentation, and OpenAPI endpoints remain public. Download operations are protected.
