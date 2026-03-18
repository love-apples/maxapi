from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VcfInfo:
    """Результат парсинга VCF строки."""

    full_name: str | None
    phones: tuple[str, ...]
    fields: dict[str, tuple[str, ...]]

    @property
    def phone(self) -> str | None:
        """Первый телефон (если есть)."""

        return self.phones[0] if self.phones else None


def parse_vcf_info(vcf_info: str) -> VcfInfo:
    """Парсит строку VCF, возвращая извлечённые поля.

    Поддерживаемые поля:
    - FN: полное имя (full_name)
    - TEL: телефоны (phones)
    """

    if not vcf_info:
        return VcfInfo(full_name=None, phones=(), fields={})

    lines = [ln.strip() for ln in vcf_info.replace("\r\n", "\n").split("\n")]
    lines = [ln for ln in lines if ln]

    fields: dict[str, list[str]] = {}

    inside = False
    for line in lines:
        upper = line.upper()
        if upper == "BEGIN:VCARD":
            inside = True
            continue
        if upper == "END:VCARD":
            break
        if not inside:
            continue

        if ":" not in line:
            continue

        left, value = line.split(":", 1)
        key = left.split(";", 1)[0].strip().upper()
        value = value.strip()
        if not key:
            continue

        fields.setdefault(key, []).append(value)

    norm_fields: dict[str, tuple[str, ...]] = {
        k: tuple(v) for k, v in fields.items()
    }

    full_name = norm_fields.get("FN", (None,))[0]
    phones = norm_fields.get("TEL", ())

    return VcfInfo(full_name=full_name, phones=phones, fields=norm_fields)
