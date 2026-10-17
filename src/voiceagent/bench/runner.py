import asyncio
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from voiceagent.bench.metrics import cer, wer
from voiceagent.providers.base import STTProvider


@dataclass
class Sample:
    audio: Path
    reference: str


@dataclass
class Row:
    provider: str
    clip: str
    reference: str
    hypothesis: str
    wer: float
    cer: float
    latency_s: float
    error: str = ""


def load_manifest(path: Path) -> list[Sample]:
    samples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        samples.append(Sample(path.parent / item["audio"], item["reference"]))
    return samples


async def _run_one(provider: STTProvider, sample: Sample) -> Row:
    try:
        result = await provider.transcribe(sample.audio.read_bytes())
    except Exception as exc:  # noqa: BLE001 - a failing clip must not abort the whole run
        return Row(provider.name, sample.audio.name, sample.reference, "", 1.0, 1.0, 0.0, repr(exc))
    return Row(
        provider.name,
        sample.audio.name,
        sample.reference,
        result.text,
        wer(sample.reference, result.text),
        cer(sample.reference, result.text),
        result.latency_s,
    )


async def run_benchmark(
    providers: dict[str, STTProvider], samples: list[Sample], concurrency: int = 4
) -> list[Row]:
    sem = asyncio.Semaphore(concurrency)

    async def guarded(p: STTProvider, s: Sample) -> Row:
        async with sem:
            return await _run_one(p, s)

    return list(
        await asyncio.gather(*(guarded(p, s) for p in providers.values() for s in samples))
    )


def summarize(rows: list[Row]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for name in sorted({r.provider for r in rows}):
        ok = [r for r in rows if r.provider == name and not r.error]
        total = sum(1 for r in rows if r.provider == name)
        if not ok:
            out[name] = {"clips": total, "errors": total}
            continue
        lat = sorted(r.latency_s for r in ok)
        out[name] = {
            "clips": total,
            "errors": total - len(ok),
            "wer": statistics.mean(r.wer for r in ok),
            "cer": statistics.mean(r.cer for r in ok),
            "latency_p50_s": statistics.median(lat),
            "latency_max_s": lat[-1],
        }
    return out


def save_rows(rows: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(asdict(r), ensure_ascii=False) for r in rows), encoding="utf-8"
    )
