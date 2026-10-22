# Video Script & B-Roll Generator

A browser app for writing short corporate video scripts. Start with an idea and it takes you through:

1. **Idea.** Describe the video and attach any reference documents (.docx, .pptx, .pdf, .txt, .md).
2. **Questions.** The model reads the idea and the documents, then asks a few follow-up questions, one at a time. Answer what you can and skip the rest; you can ask for more.
3. **Type.** It recommends a video type (Overview, Explainer or Executive) from your answers. You can switch.
4. **Script.** A voiceover script written to each section's word budget and your brand voice. Download it as Word or PDF; the file ends with the brief it was written from.

**Advanced mode** (Settings) adds two steps for the video team:

5. **Scenes.** The locked script becomes an ordered list of see-say b-roll scenes covering the whole runtime, plus a small recurring cast.
6. **Shots.** Each scene breaks down into shots with ready-to-paste image and video (LTX) prompts, and exports to a `.storyboard` file for Storyboarder.

**Live app:** https://oldgodsslumber.github.io/scriptingapp/

There's no build step, server or account. Everything is saved in your browser's local storage.

## Sign-in and the team engine (optional)

A deployment can add Firebase, following [DEPLOY.md](DEPLOY.md). People then sign in with an emailed link; only addresses at one domain can get one. Signed-in people use a shared Gemini key held on the server, with a daily limit and nothing to set up. They also get the organization's brand pack (name, voice guide, logo and colors) automatically. Without Firebase, the app works as described below.

## Getting started

1. Open the app and click **Settings**.
2. Choose an engine:
   - **Gemini:** paste a key from [Google AI Studio](https://aistudio.google.com/apikey).
   - **Local:** run a model on your own machine with Foundry Local (see below).
3. Set a **Company name**. It fills in the video types ("Why Acme") and the prompts.
4. Replace the sample **Voice document** with your brand's voice guide.

Your API key stays in your browser and is sent only to Google. Anyone using the same browser profile can read it, so don't use a shared machine.

## Running a local model (Foundry Local, macOS)

`run-proxy.command` starts [Foundry Local](https://github.com/microsoft/Foundry-Local), loads the model (`qwen3-14b` by default) and starts `foundry_cors_proxy.py` on `http://127.0.0.1:8757`. The proxy lets the browser app talk to the model.

```sh
brew tap microsoft/foundrylocal && brew install foundrylocal
./run-proxy.command        # or double-click it in Finder
```

Then choose **Settings → Local** and click **Check connection**.

- The proxy accepts requests only from `localhost` and from the origin in `APP_ORIGIN` at the top of `foundry_cors_proxy.py`. If you host your own copy, change that value.
- The proxy also serves the app at `http://127.0.0.1:8757/`. That copy keeps its own saved videos and settings, separate from the GitHub Pages copy, because browsers store data per site.

## Running it locally

Serve the folder over HTTP. Opening the file directly from disk blocks the prompt files from loading.

```sh
python3 -m http.server 8000
# open http://localhost:8000/
```

## Customizing

| File | What it controls |
| --- | --- |
| `assets/voice-guide.md` | The default voice guide (Settings can override it per browser) |
| `assets/Scene_Prompt_v5.md` | The scene-agent prompt. `{{BRAND}}`, `{{SCRIPT}}`, `{{INDUSTRY}}` and the other tokens are filled in at run time |
| `assets/Shot_Prompt_v2.md` | The shot-agent prompt |
| `assets/theme.css` | Colors and fonts |
| `index.html` | The app: markup plus one `Component` class holding all the logic; video types and word budgets are in `TYPES` |

`support.js` is the runtime that renders `index.html`. It is generated code, so don't edit it.
