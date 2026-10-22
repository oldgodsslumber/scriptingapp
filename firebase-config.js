// Firebase web config for this deployment. It identifies the project; it is not a secret (access is
// enforced by the Cloud Functions and firestore.rules). Left as null, the app runs without sign-in,
// the brand pack or the team engine, exactly as a plain static page.
export const firebaseConfig = null;

// Region the Cloud Functions are deployed to.
export const functionsRegion = 'us-central1';
