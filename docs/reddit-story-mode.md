# Reddit Story Mode

Short.ai-style Reddit story videos: paste a Reddit post URL, fetch title/body, narrate with TTS, and overlay progressive Reddit-style cards on looping local gameplay footage.

## Setup

1. Add the `[reddit]` section to `config.toml` (see `config.example.toml`):

```toml
[reddit]
gameplay_dir = "resource/gameplay"
comment_limit = 0
user_agent = "MoneyPrinterTurbo/1.3 by u/YOUR_USERNAME"
# Optional — script app at https://www.reddit.com/prefs/apps
client_id = ""
client_secret = ""
```

2. Put at least one gameplay clip (`.mp4`, `.mov`, or `.mkv`) in `resource/gameplay/`.
   Minecraft parkour / subway-surfers style loops work best. Do **not** commit copyrighted gameplay assets to the repo.

3. In the WebUI, set **Video Source** to **Reddit Story**, paste a post URL, then click **Generate Video**.
   Optionally use **Fetch Reddit Script** to preview the narration first.

## Reddit OAuth (recommended)

Create a **script** app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (no OAuth callback server needed).

1. App type: **script**
2. Redirect URI: `http://localhost:8080` (required by the form; unused)
3. Copy **client id** and **secret** into `config.toml`
4. Set `user_agent` to include your Reddit username (Reddit policy)

When credentials are set, fetch uses:

`POST https://www.reddit.com/api/v1/access_token` (client credentials)  
→ `GET https://oauth.reddit.com/r/{sub}/comments/{id}`

If OAuth fails or credentials are empty, the client falls back to the public `.json` endpoint.

## Entertainment behavior

- Title hook card, then sentence-by-sentence body cards
- No burn-in captions (cards only)
- No comments in narration or on screen
- ~2s minimum segment duration so short lines stay readable
- Muted title on the first two body cards only; later beats show the sentence alone
- Card fade/scale enter; max ~40% frame height so gameplay stays visible

## Test script

```bash
# Quick compose smoke test (no TTS) using the bundled confession fixture:
uv run python scripts/test_reddit_story.py \
  --fixture test/services/fixtures/confessions_1v1uq6u.json \
  --stage compose --duration 12

# Full end-to-end (TTS + final MP4, no captions):
uv run python scripts/test_reddit_story.py \
  --fixture test/services/fixtures/confessions_1v1uq6u.json \
  --stage full
```

### Reddit 403 note

Without OAuth, Reddit often returns **403 Blocked** for the public `.json` API from some regions/IPs. Workarounds:

1. Configure `client_id` / `client_secret` (preferred)
2. Save a fixture shaped like `test/services/fixtures/confessions_1v1uq6u.json` and pass `--fixture`
3. Use a VPN and retry live fetch

## API

`POST /api/v1/videos` with:

```json
{
  "video_subject": "Reddit Story",
  "video_source": "reddit",
  "reddit_url": "https://www.reddit.com/r/.../comments/.../",
  "video_aspect": "9:16",
  "voice_name": "en-US-EmmaNeural-Female",
  "subtitle_enabled": false
}
```

`reddit_gameplay_dir` can override the configured folder for a single request.
