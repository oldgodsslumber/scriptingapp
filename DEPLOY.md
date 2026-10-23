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

To keep a deployment's config out of the repo, put it in `private/firebase-config.js` instead (git ignores `private/`) and publish with Firebase Hosting (step 4). The repo's own `firebase-config.js` can then stay `null`.

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
GEMINI_BASE_URL=https://generativelanguage.googleapis.com
```

List every line, even `GEMINI_BASE_URL`: a non-interactive deploy stops on any setting that is missing.

`ADMIN_EMAILS` is the starting team. Add or remove the rest of the team in the Studio afterwards; that list lives in Firestore, so changing it needs no redeploy.

Then deploy:

```sh
firebase deploy --only functions,firestore:rules
```

On a project's first deploy, one function can fail with "HTTP Error: 500, Could not create Cloud Run service" while new permissions spread. Deploy that function again on its own (`firebase deploy --only functions:generate --force`). `--force` also sets up automatic deletion of old build images, which otherwise add a small monthly bill.

## 4. Publish and set up the brand pack

1. Publish the site, one of two ways:
   - **Firebase Hosting:** `firebase deploy --only hosting`. It runs `scripts/build-site.mjs` first, which copies just the app files into `.site/` and swaps in `private/firebase-config.js` if there is one. The site is at `https://<project-id>.web.app`, and sign-in works there with no extra setup. Run the same command again after every change.
   - **GitHub Pages:** commit the config in `firebase-config.js` and push. If Pages isn't on yet, go to **Settings → Pages → Deploy from a branch → `main` / root**. Add `<username>.github.io` under **Authentication → Settings → Authorized domains**.
2. Open the site, enter your email, and click the link in the email.
3. As a team member, open **Studio → Brand**. Set the company name, upload the voice guide (`.md` or `.txt`), the logo (SVG or PNG; use one that reads on a white header), and optionally a colors CSS file, then click **Save brand pack**.
4. Everyone who signs in after that gets the brand pack. People already signed in get it on their next reload.

To start with a brand pack already in place, put it in `functions/brand-seed.json` (git ignores it) as `{"name": "…", "voiceDoc": "…", "logo": "data:image/svg+xml;base64,…", "themeCss": "…", "ticketForm": "<the ticket form JSON, as a string>"}` and deploy the functions. Each part (and the ticket form, which goes to the ticketing settings, not the brand pack) is filled in on a sign-in if it's still empty, once; after that the Brand and Ticketing tabs own them.

## Optional: a ticket form

If requests go through a ticket system, upload its "new request" form as JSON under **Studio → Ticketing** and click **Save ticketing**. It's stored apart from the brand pack (in `config/ticket`), so saving one never changes the other. The last step then becomes **Ticket**: Gemini fills the form's fields from the script and answers, the requester checks them, copies them across (or drags a one-time bookmark that fills the form), pastes the case number back, and marks the video ready. Without a ticket form the last step is a plain **Submit**.

```json
{
  "name": "Tickets", "formName": "Create a Video",
  "url": "https://tickets.example.com/new",
  "caseUrl": "https://tickets.example.com/case/{case}", "casePattern": "(?:^|V\\s*-?\\s*)(\\d{4,})", "caseFormat": "V-{n}", "casePlaceholder": "e.g. V-1234",
  "formMarker": "[name^=ticket]", "dateFormat": "MM/DD/YYYY",
  "fields": [
    { "key": "title", "label": "Title", "type": "text", "name": "ticketTitle", "required": true, "max": 60, "source": "title" },
    { "key": "team", "label": "Your team", "type": "select", "name": "ticketTeam", "options": ["Marketing", "Sales"], "source": "ask", "remember": true },
    { "key": "topics", "label": "Topics", "type": "multiselect", "inputId": "topicsInput", "options": ["AI", "Cloud"], "source": "gemini", "guide": "One to three topics." },
    { "key": "requester", "label": "Requester", "type": "text", "name": "ticketRequester", "slow": true, "source": "requester" },
    { "key": "due", "label": "Due", "type": "date", "name": "ticketDue", "source": "neededBy" },
    { "key": "kind", "label": "Video type", "type": "select", "name": "ticketKind", "options": ["Overview", "Explainer", "Executive"], "source": "typeMap", "map": { "overview": "Overview", "explainer": "Explainer", "executive": "Executive" } },
    { "key": "summary", "label": "Synopsis", "type": "textarea", "name": "ticketSummary", "source": "gemini", "guide": "Three to five plain sentences." }
  ]
}
```

- `source` says where a field's value comes from: `title` and `gemini` (written by Gemini, following `guide`), `requester` (the sign-in email), `neededBy` (the Submit page's date), `typeMap` (the video type, through `map`), `fixed` (always `value`), `ask` (the requester picks; `remember` fills it in next time). Fields with no `source` are left for the requester.
- Field types: `text`, `textarea`, `select`, `radio`, `multiselect`, `checkbox`, `date`, `number`, `url`.
- The bookmark appears only when `formMarker` is set. It finds the form by that CSS selector (also inside iframes), fills fields by `name` (or `inputId` for multi-picks, which it opens with the down arrow and clicks like a person), and types the first letters of a `slow` field so its autocomplete opens.
- The case number the requester pastes is tidied with `casePattern` and `caseFormat`, and linked with `caseUrl`.

## The kickoff brief (team only)

Each script in **Studio → Scripts** has a kickoff brief: audience, goal, key message, format, description, talent, distribution, dates, people, must-haves, existing material and open questions, plus an agenda for the discovery call. It's built automatically the first time the team opens a script that's ready, from the requester's answers, script, documents, details and ticket. Team edits survive a rebuild; **Update the brief from these notes** folds call notes back in. It's stored in `scripts/{id}/kickoff/main`, which the database rules let only the team read or write. Copy it or download it as a Word file.

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
