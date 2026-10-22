# Deploying sign-in, the brand pack and the team engine

This is optional. Without it, `firebase-config.js` exports `null` and the app is a plain static page where everyone brings their own Gemini key.

With it:

- **Sign-in:** people sign in with an emailed link. Only addresses at one domain (say `example.com`) can get a link.
- **Team engine:** everyone uses one Gemini key held on the server. Nobody needs their own key, and each person has a daily limit.
- **Brand pack:** the company name, voice guide, logo and colors load automatically after sign-in. They're stored in Firebase, not in this repo.
- **Submit and the Studio:** scripts are saved to Firestore as people work, and requesters submit them as a final step. The team works in the **Studio**, where they see every script (drafts too), its brief and answers, versions and messages. They can set its status, assign it, edit it in the full editor, and write internal notes. Both sides get in-app notifications.

The brand pack, usage counts and the Gemini key go through the Cloud Functions in `functions/index.js`. `firestore.rules` lets each person reach only their own scripts, and the team reach all of them.

## 1. Create the Firebase project (console)

1. Go to <https://console.firebase.google.com>, click **Create a project**, and name it.
2. Open **Usage and billing → Details & settings → Modify plan** and choose **Blaze** (pay as you go). Cloud Functions need it. Then set a budget alert in Google Cloud Billing. Firebase's own cost for a tool this size is usually close to nothing; Gemini usage is the real cost.
3. Open **Authentication → Get started → Sign-in method → Email/Password**. Turn on **Email/Password** and **Email link (passwordless sign-in)**, then save.
4. Open **Authentication → Settings → Authorized domains** and add both:
   - your site's host, for example `yourname.github.io`
   - `127.0.0.1`, for the copy served by `run-proxy.command`
5. Open **Firestore Database → Create database**, choose **production mode**, and pick a location near your users.
6. Open **Project settings → General → Your apps**, add a **Web** app, and copy its config object.

## 2. Point the app at the project

Paste the config into `firebase-config.js`:

```js
export const firebaseConfig = { apiKey: "…", authDomain: "…", projectId: "…", appId: "…" };
export const functionsRegion = 'us-central1';
```

The web config isn't a secret: it names the project, and access is enforced on the server.

## 3. Deploy the functions and rules (command line, from the repo folder)

```sh
npm install -g firebase-tools        # once
firebase login                       # once
firebase use --add                   # pick the project you created
cd functions && npm install && cd ..

firebase functions:secrets:set GEMINI_KEY      # paste a Gemini API key from https://aistudio.google.com/apikey
```

Create `functions/.env.<your-project-id>`. Git ignores it, so the domain and admin addresses stay out of the repo.

```
ALLOWED_DOMAIN=example.com
ADMIN_EMAILS=you@example.com
DAILY_LIMIT=200
```

`ADMIN_EMAILS` is the starting team. Add or remove the rest of the team in the Studio afterwards; that list lives in Firestore, so changing it needs no redeploy.

Then deploy:

```sh
firebase deploy --only functions,firestore:rules
```

## 4. Publish and set up the brand pack

1. Push to GitHub. If GitHub Pages isn't on yet, go to **Settings → Pages → Deploy from a branch → `main` / root**.
2. Open the site, enter your email, and click the link in the email.
3. As a team member, open **Studio → Brand**. Set the company name, upload the voice guide (`.md` or `.txt`), the logo (SVG or PNG; use one that reads on a white header), and optionally a colors CSS file, then click **Save brand pack**.
4. Everyone who signs in after that gets the brand pack. People already signed in get it on their next reload.

## Things to check

- **Email delivery.** Sign-in emails come from `noreply@<project>.firebaseapp.com`. Company spam filters can quarantine them, so test with your own inbox and a colleague's first. If that's a problem, set a custom sender domain under **Authentication → Templates**.
- **Link scanners.** Some mail systems open links to scan them. Signing in only completes when the page runs in a real browser, so that's normally fine, but check it on your company's email.
- **Usage.** Each person's daily count is stored in Firestore under `usage/`. Change the limit by editing `DAILY_LIMIT` and redeploying the functions.

## Testing locally with the emulators

`functions/.env.local` and `functions/.secret.local` (both ignored by git) supply test values:

```
# functions/.env.local
ALLOWED_DOMAIN=example.com
ADMIN_EMAILS=admin@example.com
DAILY_LIMIT=50
GEMINI_BASE_URL=http://127.0.0.1:8798   # optional: a fake Gemini for tests

# functions/.secret.local
GEMINI_KEY=fake-key
```

```sh
firebase emulators:start --only auth,functions,firestore --project demo-vsg
```

To point a test copy of the site at the emulators, add `export const useEmulators = true;` to its `firebase-config.js`. The emulator doesn't send real email; it lists the sign-in links at `http://127.0.0.1:9099/emulator/v1/projects/demo-vsg/oobCodes`.
