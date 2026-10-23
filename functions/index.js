// Server side for the Video Script Generator: who may sign in, the organization's brand pack,
// and Gemini calls made with one shared key that never reaches a browser.
// Clients never touch Firestore directly (firestore.rules denies everything); it all goes through here.
const { onCall, HttpsError } = require('firebase-functions/v2/https');
const { defineSecret, defineString, defineInt } = require('firebase-functions/params');
const { initializeApp } = require('firebase-admin/app');
const { getFirestore, FieldValue } = require('firebase-admin/firestore');

initializeApp();
const db = getFirestore();

// Set at deploy time; the CLI prompts for them and keeps them in functions/.env.<project> (gitignored).
const ALLOWED_DOMAIN = defineString('ALLOWED_DOMAIN', { description: 'Email domain allowed to sign in, e.g. example.com' });
const ADMIN_EMAILS = defineString('ADMIN_EMAILS', { description: 'Comma-separated emails that can edit the brand pack' });
const DAILY_LIMIT = defineInt('DAILY_LIMIT', { default: 200, description: 'Model calls per person per day' });
const GEMINI_BASE_URL = defineString('GEMINI_BASE_URL', { default: 'https://generativelanguage.googleapis.com' });
const GEMINI_KEY = defineSecret('GEMINI_KEY');

const BRAND_DOC = 'brand/main';
const TICKET_DOC = 'config/ticket';
const LIMITS = { name: 80, voiceDoc: 200000, logo: 400000, themeCss: 100000, ticketForm: 100000, prompt: 400000 };

function emailOf(auth) { return String((auth && auth.token && auth.token.email) || '').trim().toLowerCase(); }
function domainOk(email) {
  const domain = ALLOWED_DOMAIN.value().trim().toLowerCase().replace(/^@/, '');
  return !!domain && /^[^@\s]+@[^@\s]+$/.test(email) && email.endsWith('@' + domain);
}
function adminList() { return ADMIN_EMAILS.value().split(',').map(e => e.trim().toLowerCase()).filter(Boolean); }
// Team = the admins named at deploy plus whoever the team has added in the Studio (config/team).
async function isTeam(email) {
  if (adminList().includes(email)) return true;
  const t = await db.doc('config/team').get();
  return t.exists && (t.data().emails || []).map(e => String(e).toLowerCase()).includes(email);
}
// The database rules read the allowed domain and the team list from config/; keep them in step with the deploy settings.
let configChecked = false;
async function ensureConfig() {
  if (configChecked) return;
  const domain = ALLOWED_DOMAIN.value().trim().toLowerCase().replace(/^@/, '');
  const [access, team] = await Promise.all([db.doc('config/access').get(), db.doc('config/team').get()]);
  if (!access.exists || access.data().domain !== domain) await db.doc('config/access').set({ domain }, { merge: true });
  const listed = team.exists ? (team.data().emails || []).map(e => String(e).toLowerCase()) : [];
  const missing = adminList().filter(e => !listed.includes(e));
  if (!team.exists || missing.length) await db.doc('config/team').set({ emails: listed.concat(missing) }, { merge: true });
  await seedBrand();
  await seedTicket();
  configChecked = true;
}
// A deployment can ship its starting settings as functions/brand-seed.json (git-ignored, uploaded with the
// functions). Each part of the brand pack (name, voice, logo, colors) is filled in once, if it's still empty; `seeded`
// remembers what was filled, so a part the team later clears or replaces in the Studio stays as they left it.
function readSeed() { try { return require('./brand-seed.json'); } catch (e) { return null; } }
async function seedBrand() {
  const seed = readSeed(); if (!seed) return;
  const patch = {};
  for (const k of ['name', 'voiceDoc', 'logo', 'themeCss']) {
    if (typeof seed[k] === 'string' && seed[k] && seed[k].length <= LIMITS[k]) patch[k] = seed[k];
  }
  if (!Object.keys(patch).length) return;
  const ref = db.doc(BRAND_DOC);
  await db.runTransaction(async (tx) => {
    const s = await tx.get(ref); const cur = s.exists ? s.data() : {}; const done = cur.seeded || {};
    const add = {};
    for (const [k, v] of Object.entries(patch)) if (!done[k] && !String(cur[k] || '').trim()) add[k] = v;
    if (!Object.keys(add).length) return;
    const seeded = { ...done }; Object.keys(add).forEach(k => { seeded[k] = true; });
    tx.set(ref, { ...add, seeded, updatedAt: FieldValue.serverTimestamp(), updatedBy: s.exists ? (cur.updatedBy || 'deploy') : 'deploy' }, { merge: true });
  });
}
// The ticket form has its own document. A form left in the brand pack by earlier versions moves here; otherwise the
// seed file's ticketForm fills it in once. Clearing it in the Studio is remembered, so it isn't filled in again.
async function seedTicket() {
  const seed = readSeed(); let fromSeed = seed && typeof seed.ticketForm === 'string' ? seed.ticketForm : '';
  if (fromSeed) { try { ticketFormProblem(fromSeed); } catch (e) { fromSeed = ''; } }
  const tref = db.doc(TICKET_DOC), bref = db.doc(BRAND_DOC);
  await db.runTransaction(async (tx) => {
    const [t, b] = await Promise.all([tx.get(tref), tx.get(bref)]);
    const cur = t.exists ? t.data() : {}; const legacy = b.exists ? String(b.data().ticketForm || '') : '';
    if (!String(cur.form || '').trim() && !cur.seeded) {
      const form = legacy.trim() ? legacy : fromSeed;
      if (form) tx.set(tref, { form, seeded: true, updatedAt: FieldValue.serverTimestamp(), updatedBy: legacy.trim() ? (b.data().updatedBy || 'deploy') : 'deploy' }, { merge: true });
    }
    if (b.exists && b.data().ticketForm !== undefined) tx.update(bref, { ticketForm: FieldValue.delete(), 'seeded.ticketForm': FieldValue.delete() });
  });
}
// Email-link sign-in marks the address verified: the person had to open the link in that inbox.
function requireMember(request) {
  if (!request.auth) throw new HttpsError('unauthenticated', 'Sign in first.');
  const email = emailOf(request.auth);
  if (!request.auth.token.email_verified || !domainOk(email)) throw new HttpsError('permission-denied', 'This account can’t use this app.');
  return email;
}
function today() { return new Date().toISOString().slice(0, 10); }

// Before a sign-in link is sent: is this an address that may use the app? Says yes or no, nothing else.
exports.checkEmail = onCall(async (request) => {
  const email = String((request.data && request.data.email) || '').trim().toLowerCase();
  return { ok: domainOk(email) };
});

// Shown on the sign-in screen, before anyone signs in: who the app is for (the allowed email domain and the
// organization's name) and its logo. Nothing else from the brand pack is public.
exports.signInInfo = onCall(async () => {
  const domain = ALLOWED_DOMAIN.value().trim().toLowerCase().replace(/^@/, '');
  const snap = await db.doc(BRAND_DOC).get(); const b = snap.exists ? snap.data() : {};
  return { domain, org: String(b.name || ''), logo: String(b.logo || '') };
});

// The brand pack and the ticket form, plus whether this person may edit them and how much of today's allowance is left.
exports.getBrand = onCall(async (request) => {
  const email = requireMember(request);
  await ensureConfig();
  const [snap, usage, ticket] = await Promise.all([
    db.doc(BRAND_DOC).get(),
    db.doc('usage/' + request.auth.uid + '_' + today()).get(),
    db.doc(TICKET_DOC).get(),
  ]);
  const b = snap.exists ? snap.data() : {}; const t = ticket.exists ? ticket.data() : {};
  return {
    brand: { name: b.name || '', voiceDoc: b.voiceDoc || '', logo: b.logo || '', themeCss: b.themeCss || '', updatedAt: b.updatedAt ? b.updatedAt.toMillis() : 0 },
    ticketForm: t.form || '', ticketUpdatedAt: t.updatedAt ? t.updatedAt.toMillis() : 0,
    isAdmin: await isTeam(email),
    dailyLimit: DAILY_LIMIT.value(),
    usedToday: usage.exists ? (usage.data().count || 0) : 0,
  };
});

// The ticket form: the request system's link and the fields its "new request" form has. Checked for shape only.
function ticketFormProblem(text) {
  let t; try { t = JSON.parse(text); } catch (e) { throw new HttpsError('invalid-argument', 'The ticket form must be JSON.'); }
  const bad = m => { throw new HttpsError('invalid-argument', 'Ticket form: ' + m); };
  if (!t || typeof t !== 'object' || Array.isArray(t)) bad('expected an object.');
  if (!/^https:\/\//.test(String(t.url || ''))) bad('"url" must be an https link.');
  if (!Array.isArray(t.fields) || !t.fields.length || t.fields.length > 60) bad('"fields" must list 1 to 60 fields.');
  for (const f of t.fields) {
    if (!f || typeof f.key !== 'string' || typeof f.label !== 'string') bad('every field needs a "key" and a "label".');
    if (!['text', 'textarea', 'select', 'radio', 'multiselect', 'checkbox', 'date', 'number', 'url'].includes(f.type)) bad('field "' + f.key + '" has an unknown type.');
    if (f.options !== undefined && !(Array.isArray(f.options) && f.options.every(o => typeof o === 'string'))) bad('the options for "' + f.key + '" must be a list of text.');
  }
}

// Admins only. Fields left out of the request are kept; an empty string clears one.
exports.saveBrand = onCall(async (request) => {
  const email = requireMember(request);
  if (!(await isTeam(email))) throw new HttpsError('permission-denied', 'Only the team can change the brand pack.');
  const d = request.data || {};
  const patch = {};
  for (const k of ['name', 'voiceDoc', 'logo', 'themeCss']) {
    if (d[k] === undefined) continue;
    if (typeof d[k] !== 'string') throw new HttpsError('invalid-argument', k + ' must be text.');
    if (d[k].length > LIMITS[k]) throw new HttpsError('invalid-argument', k + ' is too large.');
    patch[k] = d[k];
  }
  if (patch.logo && !/^data:image\/(svg\+xml|png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(patch.logo)) throw new HttpsError('invalid-argument', 'The logo must be an SVG, PNG, JPEG or WebP image.');
  if (patch.themeCss && /<\/?style|<script|@import\s+url\(\s*['"]?javascript:/i.test(patch.themeCss)) throw new HttpsError('invalid-argument', 'The theme must be plain CSS.');
  await db.doc(BRAND_DOC).set({ ...patch, updatedAt: FieldValue.serverTimestamp(), updatedBy: email }, { merge: true });
  return { ok: true };
});

// Team only. The ticket form as JSON text; an empty string removes it (requesters then get a plain Submit step).
exports.saveTicketForm = onCall(async (request) => {
  const email = requireMember(request);
  if (!(await isTeam(email))) throw new HttpsError('permission-denied', 'Only the team can change ticketing.');
  const form = String((request.data || {}).form ?? '');
  if (form.length > LIMITS.ticketForm) throw new HttpsError('invalid-argument', 'The ticket form is too large.');
  if (form.trim()) ticketFormProblem(form);
  await db.doc(TICKET_DOC).set({ form: form.trim(), seeded: true, updatedAt: FieldValue.serverTimestamp(), updatedBy: email }, { merge: true });
  return { ok: true };
});

// A Gemini call with the shared key, counted against the person's daily allowance.
exports.generate = onCall({ secrets: [GEMINI_KEY], timeoutSeconds: 540, memory: '256MiB' }, async (request) => {
  const email = requireMember(request);
  const d = request.data || {};
  const prompt = String(d.prompt || '');
  if (!prompt) throw new HttpsError('invalid-argument', 'Nothing to send.');
  if (prompt.length > LIMITS.prompt) throw new HttpsError('invalid-argument', 'The request is too long. Remove some reference material and try again.');
  const model = String(d.model || 'gemini-3.8-flash').replace(/^models\//, '');
  if (!/^(gemini|gemma)-[\w.-]{1,60}$/i.test(model)) throw new HttpsError('invalid-argument', 'Unknown model.');
  const gemma = /^gemma/i.test(model);

  const usageRef = db.doc('usage/' + request.auth.uid + '_' + today());
  const limit = DAILY_LIMIT.value();
  await db.runTransaction(async (tx) => {
    const s = await tx.get(usageRef);
    const count = s.exists ? (s.data().count || 0) : 0;
    if (count >= limit) throw new HttpsError('resource-exhausted', 'You’ve reached today’s limit of ' + limit + ' generations. It resets at midnight UTC.');
    tx.set(usageRef, { count: count + 1, email, day: today(), last: FieldValue.serverTimestamp() }, { merge: true });
  });

  const generationConfig = {};
  if (gemma && typeof d.temperature === 'number') generationConfig.temperature = Math.max(0, Math.min(2, d.temperature));
  if (/^gemini-([3-9]|\d{2,})/i.test(model) && ['low', 'medium', 'high'].includes(d.thinking)) generationConfig.thinkingConfig = { thinkingLevel: d.thinking };
  if (d.json && !gemma) { generationConfig.responseMimeType = 'application/json'; if (d.schema && typeof d.schema === 'object') generationConfig.responseSchema = d.schema; }

  let res;
  try {
    res = await fetch(GEMINI_BASE_URL.value().replace(/\/+$/, '') + '/v1beta/models/' + encodeURIComponent(model) + ':generateContent', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': GEMINI_KEY.value() },
      body: JSON.stringify({ contents: [{ role: 'user', parts: [{ text: prompt }] }], generationConfig }),
    });
  } catch (e) {
    throw new HttpsError('unavailable', 'Couldn’t reach Gemini. Try again in a moment.');
  }
  if (!res.ok) {
    const t = await res.text(); let msg = t; try { msg = JSON.parse(t).error.message || t; } catch (e) { /* raw text */ }
    if (res.status === 404) msg += ' (“' + model + '” may be retired; pick another model in Settings.)';
    throw new HttpsError(res.status === 429 ? 'resource-exhausted' : 'internal', 'Gemini ' + res.status + ': ' + String(msg).slice(0, 500));
  }
  const data = await res.json();
  const cand = ((data || {}).candidates || [])[0] || {};
  const text = ((cand.content || {}).parts || []).filter(p => !p.thought).map(p => p.text || '').join('').trim();
  const block = ((data || {}).promptFeedback || {}).blockReason || '';
  return { text, finishReason: cand.finishReason || '', blockReason: block };
});
