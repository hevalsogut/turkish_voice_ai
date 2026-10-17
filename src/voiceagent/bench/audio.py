import subprocess
from pathlib import Path


def telephonize(src: Path, dst: Path) -> None:
    """Degrade a clip to phone quality: 8 kHz mono, 300-3400 Hz band, mu-law round trip."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    mulaw = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
            "-af", "highpass=f=300,lowpass=f=3400",
            "-ar", "8000", "-ac", "1", "-c:a", "pcm_mulaw", "-f", "wav", "pipe:1",
        ],
        check=True,
        capture_output=True,
    ).stdout
    # Decode back to PCM so every provider accepts the file.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "wav", "-i", "pipe:0",
         "-c:a", "pcm_s16le", str(dst)],
        input=mulaw,
        check=True,
    )
