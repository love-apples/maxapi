"""Тесты, проверяющие, что отображение фикстур покрывает все
типы из UpdateUnion.
"""

from typing import Annotated, get_args, get_origin

from maxapi.types.updates import UpdateUnion

from tests.conftest import _FIXTURE_NAME_BY_UPDATE


def _extract_union_classes(typ):
    """Извлечь классы моделей из Annotated[Union[...]]
    (UpdateUnion).
    """
    origin = get_origin(typ)
    # Если тип — Annotated, то первый аргумент — базовый тип
    if origin is Annotated:
        typ = get_args(typ)[0]

    origin = get_origin(typ)
    if origin is None:
        # одиночный тип
        return (typ,)

    return get_args(typ)


def _get_update_type_default(cls):
    """Вернуть значение по умолчанию для поля `update_type`."""
    mf = getattr(cls, "model_fields", None)
    if isinstance(mf, dict) and "update_type" in mf:
        field_info = mf["update_type"]
        # field_info может быть mapping с полем 'default'
        if isinstance(field_info, dict):
            default = field_info.get("default")
        else:
            default = getattr(field_info, "default", None)
        if default is not None:
            return default

    return getattr(cls, "update_type", None)


def test_fixtures_cover_all_update_union_types():
    """Убедиться, что у каждой модели из UpdateUnion есть запись
    в маппинге фикстур.

    Требуем, чтобы маппинг фикстур был надмножеством типов
    обновлений, объявленных в моделях `UpdateUnion` (т.е. для каждой
    модели был соответствующий fixture). Дополнительные ключи в
    маппинге считаются допустимыми.
    """
    classes = _extract_union_classes(UpdateUnion)

    union_update_types = set()
    for cls in classes:
        ut = _get_update_type_default(cls)
        assert ut is not None, (
            "Не удалось определить значение `update_type` по умолчанию для "
            f"модели обновления: {cls.__name__!r}"
        )
        union_update_types.add(ut)

    fixture_update_types = set(_FIXTURE_NAME_BY_UPDATE.keys())

    missing = union_update_types - fixture_update_types
    extra = fixture_update_types - union_update_types

    missing_sorted = sorted(missing, key=lambda x: getattr(x, "name", str(x)))
    extra_sorted = sorted(extra, key=lambda x: getattr(x, "name", str(x)))

    assert not missing, (
        "В маппинге фикстур отсутствуют записи для некоторых типов\n"
        "обновлений, объявленных в UpdateUnion:\n"
        f"Отсутствующие фикстуры: {missing_sorted}\n"
        f"Дополнительные фикстуры (допускаются): {extra_sorted}"
    )
