# Usage

How to read with Paradox, and how to use the TTS engine on its own.

---

## Reading on Novel Phoenix

1. Start the server: double-click **`Start server.bat`** and wait for
   *Model ready*.
2. Open a chapter on [novelphoenix.com](https://novelphoenix.com/).
3. The **Paradox** bar appears in the bottom-right corner and begins
   generating the chapter.
4. If the browser blocks autoplay the first time, press **▶** once. After that,
   chapter changes play automatically.

The chapter is synthesized as a whole, so playback does not stutter while later
paragraphs are generated.

---

## The control bar

| Button | Action |
| --- | --- |
| ⏮ | Previous chapter |
| ▶ / ❚❚ | Play / pause |
| ■ | Stop and reset to the start |
| ⏭ | Next chapter |
| ⚙ | Open settings |
| progress bar | Position within the chapter |

### Next and previous without a reload

By default the extension **switches chapters in place**. Clicking the site's
Next/Prev buttons (or the bar's own arrows) fetches the neighbouring chapter
HTML, replaces the text, updates the address bar, and starts generating — all
without a page reload. That is what lets audio keep playing and autoplay keep
working. The middle-of-page chapter dropdown is left to the site itself.

Turn this off with **Switch chapters in place** if you prefer full page loads.

### Auto-advance

With **Continue to next chapter** enabled, when the audio reaches the end the
extension loads the next chapter and continues reading. Disable it if you want
to stop at chapter boundaries.

---

## Settings

Open the settings from the toolbar popup or the bar's ⚙ button.

| Setting | Default | Meaning |
| --- | --- | --- |
| Reader enabled | on | Show the bar and do anything at all |
| Read when a chapter opens | on | Generate and try to play on load |
| Continue to next chapter | on | Auto-advance when audio ends |
| Switch chapters in place | on | Intercept Next/Prev instead of reloading |
| Voice | `af_heart` | Any voice reported by the server (54 in v1.0) |
| Speed | `1.0` | 0.5 – 2.0 |
| Port | `8756` | Must match the server |

Settings are stored in the browser and apply to every Novel Phoenix tab.

### Choosing a voice

Voice names follow `XY_name`, where `X` is the language and `Y` is the gender:

| Code | Language | Code | Language |
| --- | --- | --- | --- |
| `a` | American English | `i` | Italian |
| `b` | British English | `j` | Japanese |
| `e` | Spanish | `p` | Brazilian Portuguese |
| `f` | French | `z` | Mandarin (extra model) |
| `h` | Hindi | | |

Gender is `f` or `m`. Examples: `af_heart` (US female, the default),
`am_michael` (US male), `bf_emma` (UK female), `bm_george` (UK male).

Mandarin voices need the extra model: `.venv\Scripts\python Kokoro-TTS\download_models.py --zh`.

---

## Standalone text-to-speech

The engine works without the browser extension.

### Desktop app

Double-click **`Kokoro TTS.bat`**. Type or paste text, pick a voice and speed,
then **Speak**. Use **Save audio…** to export WAV, MP3, FLAC or OGG, and
**Voices…** to browse every installed voice.

### Command line

```bat
:: Speak a phrase and play it
.venv\Scripts\python Kokoro-TTS\tts.py "Hello from Paradox" --play

:: Pick a voice and speed
.venv\Scripts\python Kokoro-TTS\tts.py "Hello" -v bm_george -s 0.95 --play

:: Read a text file into an MP3
.venv\Scripts\python Kokoro-TTS\tts.py -f chapter.txt -o output\chapter.mp3

:: Read standard input
type notes.txt | .venv\Scripts\python Kokoro-TTS\tts.py -f - -o output\notes.wav

:: List every voice
.venv\Scripts\python Kokoro-TTS\tts.py --list-voices

:: Verify the install and show the realtime factor
.venv\Scripts\python Kokoro-TTS\tts.py --selftest
```

Convenience launchers:

```bat
speak.bat "Hello from Paradox"
speak.bat "Hello" -v af_bella -s 1.1
speak_clipboard.bat
```

### CLI options

| Option | Meaning |
| --- | --- |
| `text...` | Words to speak (or omit to read stdin) |
| `-f, --file` | Read text from a UTF-8 file, or `-` for stdin |
| `-o, --out` | Output path; suffix selects WAV/MP3/FLAC/OGG |
| `-v, --voice` | Voice name (default `af_heart`); blend with `af_heart,af_bella` |
| `-s, --speed` | 0.5 – 2.0 (default `1.0`) |
| `-l, --lang` | Force a language code instead of inferring from the voice |
| `-d, --device` | `auto`, `cuda` or `cpu` |
| `--model-dir` | Use a different model folder |
| `--format` | Format when `-o` has no suffix |
| `--play` | Play through the default output device |
| `--list-voices` | Print installed voices |
| `--selftest` | Generate a test line and report speed |
| `-q, --quiet` | Only print the output path |

---

## Output locations

Generated audio defaults to the project's `output/` folder (created on demand).
The desktop app writes its log there as well. Override with `KOKORO_OUTPUT_DIR`.

---

## Tips

- A GPU makes a large difference. A whole chapter can be generated in seconds
  on CUDA; the CPU takes noticeably longer but still works.
- First playback after starting the server includes a short warm-up. Later
  chapters are faster.
- Use **⚙ → Port** if another program already uses `8756`.
- The server logs each request with character count, audio length and speed, so
  the console tells you how each chapter performed.
- For long offline material, prefer `tts.py -f big.txt -o output\big.mp3`.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Bar says **Server offline** | Start `Start server.bat`; confirm the port matches. |
| Audio does not start until ▶ | Browser autoplay policy — click ▶ once per tab. |
| Wrong or missing chapter text | Reload the tab. Confirm the URL is `novelphoenix.com`. |
| Choppy first words | The chapter was still generating; later chapters use the warm model. |
| No sound | Check the Windows output device and test with `tools\check_server.py`. |
| Voice not found | Run `download_models.py`, then reopen the popup. |