import functools
import inspect
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from livekit.agents import Agent, RunContext, function_tool

from voiceagent.agent.prompts import build_system_prompt
from voiceagent.clinic.handoff import StaffNotifier
from voiceagent.clinic.models import ClinicConfig, StaffMessage
from voiceagent.clinic.phone import normalize_phone, phone_to_speech
from voiceagent.clinic.scheduler import AppointmentStore, SlotUnavailableError


def reported(fn):
    """Report every tool call (name, arguments, result) to the dashboard's live view."""
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    async def wrapper(self, context, *args, **kwargs):
        result = await fn(self, context, *args, **kwargs)
        bound = sig.bind(self, context, *args, **kwargs)
        bound.apply_defaults()
        call_args = {k: v for k, v in bound.arguments.items() if k not in ("self", "context")}
        self._on_event({"type": "tool", "name": fn.__name__, "args": call_args, "result": result})
        return result

    return wrapper


class ClinicAgent(Agent):
    def __init__(
        self,
        *,
        config: ClinicConfig,
        knowledge: str,
        store: AppointmentStore,
        notifier: StaffNotifier,
        on_event: Callable[[dict], None] | None = None,
        on_hangup: Callable[[], None] | None = None,
    ) -> None:
        self._on_hangup = on_hangup or (lambda: None)
        self._on_event = on_event or (lambda event: None)
        self._config = config
        self._store = store
        self._notifier = notifier
        self._tz = ZoneInfo(config.timezone)
        super().__init__(
            instructions=build_system_prompt(config, knowledge, datetime.now(self._tz))
        )

    @function_tool
    @reported
    async def check_availability(self, context: RunContext, date: str, department: str) -> str:
        """Bir gün ve bölüm için boş randevu saatlerini döndürür.

        Args:
            date: Gün, YYYY-MM-DD biçiminde.
            department: Bölüm adı (Dahiliye, Kardiyoloji, Göz Hastalıkları, Diş).
        """
        try:
            day = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return "Tarih biçimi geçersiz. YYYY-MM-DD kullan."
        today = datetime.now(self._tz).date()
        if day < today:
            return "Bu tarih geçmişte. Takvime bakıp doğru tarihi bul."
        if day.weekday() not in self._config.open_days:
            return "Klinik o gün kapalı. Başka bir gün öner."
        slots = self._store.free_slots(day, department)
        if not slots:
            return "O gün tüm saatler dolu. Başka bir gün öner."
        return "Boş saatler: " + ", ".join(f"{s:%H:%M}" for s in slots)

    @function_tool
    @reported
    async def book_appointment(
        self,
        context: RunContext,
        patient_name: str,
        patient_phone: str,
        department: str,
        date: str,
        time: str,
    ) -> str:
        """Randevu oluşturur. Tüm bilgiler arayanla teyit edildikten sonra çağır.

        Args:
            patient_name: Hastanın adı ve soyadı.
            patient_phone: Geri dönüş telefon numarası, 11 hane, 05 ile başlar, yalnızca rakamlar.
            department: Bölüm adı.
            date: Gün, YYYY-MM-DD biçiminde.
            time: Saat, HH:MM biçiminde.
        """
        phone = normalize_phone(patient_phone)
        if phone is None:
            return "Telefon numarası geçersiz. Arayandan numarayı baştan iste."
        try:
            start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=self._tz)
        except ValueError:
            return "Tarih veya saat biçimi geçersiz."
        try:
            appt = self._store.book(
                patient_name=patient_name,
                patient_phone=phone,
                department=department,
                start=start,
            )
        except SlotUnavailableError:
            return "Bu saat dolu veya geçersiz. Başka bir saat öner."
        return f"Randevu oluşturuldu: {appt.department}, {appt.start:%Y-%m-%d %H:%M}, no {appt.id}."

    @function_tool
    @reported
    async def confirm_phone(self, context: RunContext, phone: str) -> str:
        """Arayanın söylediği telefon numarasını doğrular ve sesli okunuşunu verir.

        Numarayı arayandan aldıktan hemen sonra çağır. Dönen okunuşu aynen oku, kendin rakam
        okumaya çalışma.

        Args:
            phone: Arayanın söylediği numara, rakamlara çevrilmiş (örn. 05540219870).
        """
        normalized = normalize_phone(phone)
        if normalized is None:
            return "Numara geçersiz veya eksik. Arayandan numarayı baştan, yavaşça iste."
        return (
            "Geçerli. Arayana yalnızca şu okunuşu aynen oku ve doğru mu diye sor, başka rakam "
            f"söyleme: {phone_to_speech(normalized)}"
        )

    @function_tool
    @reported
    async def end_call(self, context: RunContext) -> None:
        """Görüşmeyi bitirir. Arayan başka bir isteği olmadığını söylediğinde,
        önce veda cümleni söyle, sonra bu aracı çağır."""
        await context.wait_for_playout()  # let the goodbye finish
        self._on_hangup()
        # Returning nothing tells the framework not to generate another reply.

    @function_tool
    @reported
    async def take_message(
        self,
        context: RunContext,
        caller_phone: str,
        summary: str,
        unresolved: str,
        caller_name: str = "",
        urgent: bool = False,
    ) -> str:
        """Çözemediğin veya personelin bilmesi gereken bir konuyu not alıp iletir.

        Yalnızca arayanın adını ve numarasını aldıktan sonra çağır.

        Args:
            caller_phone: Arayanın geri dönüş numarası (rakamlar).
            summary: Personelin tek bakışta anlayacağı net özet (kim, ne istiyor, hangi bölüm,
                ne zaman müsait).
            unresolved: Çözülemeyen konu, personelden ne bekleniyor.
            caller_name: Arayanın adı, biliniyorsa.
            urgent: Acil bir durum varsa true.
        """
        phone = normalize_phone(caller_phone)
        if phone is None:
            return "Telefon numarası geçersiz. Arayandan numarayı baştan iste."
        await self._notifier.notify(
            StaffMessage(
                tenant_id=self._config.tenant_id,
                caller_name=caller_name,
                caller_phone=phone,
                summary=summary,
                unresolved=unresolved,
                urgent=urgent,
                created_at=datetime.now(self._tz),
            )
        )
        return "Mesaj personele iletildi. Arayana en kısa sürede geri döneceklerini söyle."
