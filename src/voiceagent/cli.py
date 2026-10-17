import asyncio
import json
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
