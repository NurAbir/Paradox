# Checksums (SHA-256)

Paradox keeps large model files out of git, so it verifies them by hash after
download. The values below belong to the canonical
[hexgrad/Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) release used by
version 1.0.0.

## Model files

| File | SHA-256 |
| --- | --- |
| `models/Kokoro-82M/kokoro-v1_0.pth` | `496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4` |
| `models/Kokoro-82M/config.json` | `5abb01e2403b072bf03d04fde160443e209d7a0dad49a423be15196b9b43c17f` |

The voice packs (`*.pt`, about 0.5 MB each) are small and are not pinned
individually; a corrupt one is reported by the engine at load time.

## Verify after setup

`download_models.py` checks these hashes automatically after downloading. You
can re-check at any time:

```bat
.venv\Scripts\python Kokoro-TTS\download_models.py --check
```

A healthy install prints:

```
[ok] v1.0 ...\models\Kokoro-82M  54 voices, 339.0 MB
[ok] sha256 Kokoro-82M/config.json
[ok] sha256 Kokoro-82M/kokoro-v1_0.pth
```

If a hash does not match, delete the `models\Kokoro-82M` folder and run setup
again; the downloader resumes and re-verifies.

## Verify a release archive

Release zips are published with a sidecar `*.zip.sha256` file. Check it before
extracting:

```bat
:: Windows
certutil -hashfile Paradox-v1.0.0.zip SHA256

:: PowerShell
Get-FileHash .\Paradox-v1.0.0.zip -Algorithm SHA256
```

Compare the printed value with the contents of `Paradox-v1.0.0.zip.sha256`.

## Generate a manifest for any files

`tools/checksums.py` writes the standard `sha256sum` format:

```bat
:: every file git tracks
.venv\Scripts\python tools\checksums.py --write SHA256SUMS

:: specific release artifacts
.venv\Scripts\python tools\checksums.py Paradox-v1.0.0.zip
```

Verify a manifest with:

```bat
.venv\Scripts\python tools\checksums.py --check SHA256SUMS
```

> **Line endings.** Files are hashed in binary mode. On Windows git checks out
> `.bat` and `.ps1` with CRLF, so a manifest generated on Linux will not match
> a Windows checkout. Hash release archives rather than source trees when the
> result must be portable.