# Video Script & B-Roll Generator

A browser app for planning short corporate videos. Start with an idea and it takes you through:

1. **Script.** Pick a video type (Overview, Explainer or Executive), answer the prep questions, and get a voiceover script written to each section's word budget and your brand voice.
2. **Scenes.** The locked script becomes an ordered list of see-say b-roll scenes covering the whole runtime, plus a small recurring cast.
3. **Shots.** Each scene breaks down into shots with ready-to-paste image and video (LTX) prompts.

Export at any step, including a `.storyboard` file for Storyboarder.

**Live app:** https://oldgodsslumber.github.io/scriptingapp/

There's no build step, server or account. Everything is saved in your browser's local storage.

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
