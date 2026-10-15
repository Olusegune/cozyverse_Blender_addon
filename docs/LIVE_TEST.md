# Testing against the real services

Everything in CozyVerse's AI and 3D generation paths is tested against a faked network. This checker is how you (or I, with your keys set) prove they work against the real thing, safely.

It runs outside Blender, never prints your key, shows exactly what would be sent, and sends nothing until you type `YES`.

## Set a key for this terminal only

In PowerShell (the key lives only in that window and is gone when you close it):

```powershell
$env:ANTHROPIC_API_KEY = "paste-your-key-here"
```

Other variables: `OPENAI_API_KEY`, `CUSTOM_LLM_API_KEY`, `TRIPO_API_KEY`, `MESHY_API_KEY`. Never paste keys into chat or into a command line.

## The checks

From the repository folder:

```powershell
# 1. See what would be sent. Nothing is sent.
python tools/live_provider_check.py plan --dry-run

# 2. One real planning call. Costs a fraction of a cent. Expect "PASS: a live model returned a valid Scene Blueprint."
python tools/live_provider_check.py plan

# 3. One real follow-up call ("more flowers, less clutter, warmer light").
python tools/live_provider_check.py followup

# OpenAI-compatible servers need a model name; custom ones also an address.
python tools/live_provider_check.py plan --provider openai --model <model name>
python tools/live_provider_check.py plan --provider custom --model <model> --base-url http://localhost:1234

# 4. One real 3D generation. Spends real credits (about 20), capped. Downloads one GLB to work/live_check/.
python tools/live_provider_check.py generate --provider tripo --max-credits 20
python tools/live_provider_check.py generate --provider meshy --max-credits 20
```

## What each check proves

| Check | Passing means |
|---|---|
| `plan` | The provider accepted the request, answered, and its answer passed the Director's strict validation. |
| `followup` | The answer came back as allowlisted commands only; anything else was dropped and reported. |
| `generate` | The job was accepted, finished, and produced a valid GLB from an approved host that CozyVerse can import. |

## If something fails

The tool prints a plain-words reason (wrong key, model not found, rate limit, unexpected reply shape) and exits with an error. For the 3D providers, a failure may mean their API has changed since this add-on's request format was written; the message plus the failing step is exactly what is needed to fix it.

## Inside Blender

After a check passes, the same path is available in the add-on: Settings → choose the provider and model, enter your key for the session, then turn on **Plan with AI** on the Create tab. You will see the same "this will be sent" list before anything leaves your computer.
