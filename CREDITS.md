# Credits

Paradox exists because of the following open projects and their authors. The
audio it produces is generated entirely by **Kokoro**, an open text-to-speech
model; Paradox is only the local server and browser front end around it.

## Text-to-speech model and engine

- **[hexgrad/Kokoro-TTS](https://huggingface.co/spaces/hexgrad/Kokoro-TTS)** —
  the reference Kokoro TTS space. The `Kokoro-TTS/` folder in this repository is
  a trimmed, self-contained copy of that engine, adapted to run headless and be
  called from the local server.
- **[hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)** — the
  82-million-parameter model weights and voice packs downloaded by
  `Kokoro-TTS/download_models.py`.
- **[hexgrad/kokoro](https://pypi.org/project/kokoro/)** — the Python package
  (`KModel`, `KPipeline`) used to load and run the model.
- **[hexgrad/misaki](https://pypi.org/project/misaki/)** — the grapheme-to-
  phoneme front end that prepares English, Chinese and other languages.

## Libraries

- **[PyTorch](https://pytorch.org/)** — tensor runtime, CUDA and model loading.
- **[soundfile](https://pypi.org/project/soundfile/)** / **libsndfile** — audio
  file writing (WAV, FLAC, OGG, MP3).
- **[NumPy](https://numpy.org/)** — audio buffers and sample handling.
- **[Hugging Face Hub](https://huggingface.co/docs/huggingface_hub)** — model
  download helper used during setup.
- **[FFmpeg](https://ffmpeg.org/)** — optional; used for higher-quality MP3
  encoding when it is on `PATH`.

## Content

Paradox is a reading aid. **This project is not affiliated with
[Novel Phoenix](https://novelphoenix.com/)** or any other reading site.
All chapters, stories and characters belong to their respective authors and
publishers. Paradox only reads text that is already displayed in your browser,
for your own personal use.

## License

Paradox is released under the [MIT License](LICENSE). The third-party projects
above keep their own licenses — please review them before redistributing.
