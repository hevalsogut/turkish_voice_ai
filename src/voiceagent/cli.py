import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from voiceagent.bench.audio import telephonize
from voiceagent.bench.runner import load_manifest, run_benchmark, save_rows, summarize
from voiceagent.config import get_settings
from voiceagent.providers.stt import available_stt_providers

app = typer.Typer(no_args_is_help=True)
console = Console()

BENCH_DIR = Path("data/stt_bench")


@app.command("stt-bench")
def stt_bench(
    manifest: Path = typer.Option(BENCH_DIR / "manifest.jsonl", help="JSONL: audio, reference"),
    only: list[str] = typer.Option([], "--only", help="Restrict to these providers"),
    concurrency: int = typer.Option(4),
) -> None:
    """Compare Turkish STT providers on your clips (WER, CER, latency)."""
    providers = available_stt_providers(get_settings())
    if only:
        providers = {k: v for k, v in providers.items() if k in only}
    if not providers:
        console.print("[red]No providers configured. Add API keys to .env[/red]")
        raise typer.Exit(1)
    samples = load_manifest(manifest)
    if not samples:
        console.print(f"[red]No samples in {manifest}[/red]")
        raise typer.Exit(1)

    rows = asyncio.run(run_benchmark(providers, samples, concurrency))
    save_rows(rows, manifest.parent / "results" / "latest.jsonl")

    table = Table(title=f"Turkish STT benchmark ({len(samples)} clips)")
    for col in ("provider", "WER", "CER", "p50 latency", "max latency", "errors"):
        table.add_column(col)
    for name, s in summarize(rows).items():
        if "wer" not in s:
            table.add_row(name, "-", "-", "-", "-", str(int(s["errors"])))
            continue
        table.add_row(
            name, f"{s['wer']:.1%}", f"{s['cer']:.1%}", f"{s['latency_p50_s']:.2f}s",
            f"{s['latency_max_s']:.2f}s", str(int(s["errors"])),
        )
    console.print(table)
    console.print("Per-clip details: data/stt_bench/results/latest.jsonl")


@app.command("telephonize")
def telephonize_cmd(
    src_dir: Path = typer.Argument(..., help="Folder of clean recordings"),
    dst_dir: Path = typer.Argument(BENCH_DIR / "clips", help="Output folder"),
) -> None:
    """Convert clean recordings to 8 kHz phone-quality audio."""
    files = sorted(p for p in src_dir.iterdir() if p.suffix.lower() in {".wav", ".m4a", ".mp3"})
    for f in files:
        telephonize(f, dst_dir / f"{f.stem}.wav")
    console.print(f"Converted {len(files)} files -> {dst_dir}")


@app.command("make-manifest")
def make_manifest(
    script: Path = typer.Option(BENCH_DIR / "script.tr.txt"),
    clips_dir: Path = typer.Option(BENCH_DIR / "clips"),
    out: Path = typer.Option(BENCH_DIR / "manifest.jsonl"),
) -> None:
    """Build the manifest from script lines 'NN|sentence' and clips named NN.wav."""
    lines = []
    for raw in script.read_text(encoding="utf-8").splitlines():
        if "|" not in raw:
            continue
        idx, sentence = raw.split("|", 1)
        clip = clips_dir / f"{idx.strip()}.wav"
        if clip.exists():
            lines.append(
                json.dumps(
                    {"audio": f"clips/{clip.name}", "reference": sentence.strip()},
                    ensure_ascii=False,
                )
            )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"Wrote {len(lines)} samples -> {out}")


@app.command("dev")
def dev() -> None:
    """Start everything for local testing: voice server, voice worker, and the dashboard."""
    settings = get_settings()
    if not shutil.which("livekit-server"):
        console.print("[red]livekit-server not found. Install it with: brew install livekit[/red]")
        raise typer.Exit(1)

    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "LIVEKIT_URL": settings.livekit_url,
        "LIVEKIT_API_KEY": settings.livekit_api_key,
        "LIVEKIT_API_SECRET": settings.livekit_api_secret,
    }
    commands = {
        "livekit": ["livekit-server", "--dev", "--bind", "127.0.0.1"],
        "worker": [sys.executable, "-m", "voiceagent.agent.main", "start"],
        "web": [
            sys.executable, "-m", "uvicorn", "voiceagent.web.app:app",
            "--host", "127.0.0.1", "--port", str(settings.web_port),
        ],
    }
    procs: dict[str, subprocess.Popen] = {}

    def stop_all(*_: object) -> None:
        for proc in procs.values():
            if proc.poll() is None:
                proc.terminate()

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    for name, cmd in commands.items():
        log = (log_dir / f"{name}.log").open("w")
        procs[name] = subprocess.Popen(
            cmd, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL
        )
        if name == "livekit":
            time.sleep(1.5)  # the worker needs the server up to register

    console.print(f"[green]Dashboard: http://127.0.0.1:{settings.web_port}[/green]")
    console.print(f"Logs in {log_dir}/ . Press Ctrl+C to stop everything.")
    try:
        while all(p.poll() is None for p in procs.values()):
            time.sleep(1)
        dead = [n for n, p in procs.items() if p.poll() is not None]
        console.print(f"[red]{', '.join(dead)} exited. See {log_dir}/{dead[0]}.log[/red]")
    finally:
        stop_all()
        for proc in procs.values():
            proc.wait(timeout=10)
