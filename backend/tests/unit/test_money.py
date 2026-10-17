from decimal import Decimal

import pytest

from app.services.money import (
    allocate,
    format_brl,
    from_decimal,
    from_float,
    parse_brl,
    to_decimal,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("R$ 1.234,56", 123456),  # PT-BR com milhar
        ("1.234,56", 123456),
        ("1,234.56", 123456),  # US
        ("1234.56", 123456),
        ("0,01", 1),
        ("-45,90", -4590),
        ("R$ -45,90", -4590),
        # Só ponto é ambíguo; num extrato PT-BR grupo de 3 dígitos é milhar.
        ("1.000", 100000),  # mil reais, não R$ 1,00
        ("1.234.567", 123456700),
        ("1234.56", 123456),  # 2 dígitos finais: decimal
        ("0.5", 50),
        ("", None),
        ("abc", None),
        (None, None),
    ],
)
def test_parse_brl(text, expected):
    assert parse_brl(text) == expected


def test_from_float_does_not_inherit_binary_noise():
    # Decimal(0.1) seria 0.1000000000000000055511151231257827...
    assert from_float(0.1) == 10
    assert from_float(12275.19) == 1227519
    assert from_float(1e-3) == 0  # abaixo de meio centavo


def test_from_decimal_rounds_half_up():
    assert from_decimal(Decimal("0.005")) == 1  # meio centavo sobe
    assert from_decimal(Decimal("0.004")) == 0
    assert from_decimal(Decimal("2.675")) == 268  # em float daria 267


def test_to_decimal_and_format():
    assert to_decimal(123456) == Decimal("1234.56")
    assert format_brl(123456) == "R$ 1.234,56"
    assert format_brl(-4590) == "-R$ 45,90"
    assert format_brl(0) == "R$ 0,00"
    assert format_brl(5) == "R$ 0,05"


# ---------- allocate: o coração da garantia ----------


def test_allocate_conserves_total_when_not_divisible():
    # 100 centavos entre 3 pesos iguais: 34/33/33, nunca 33/33/33.
    parts = allocate(100, [1, 1, 1])
    assert sum(parts) == 100
    assert parts == [34, 33, 33]


def test_allocate_proportional_to_income():
    # Ana 5000, Bruno 3000 sobre R$ 1.200,00 -> 750,00 / 450,00 (exato)
    assert allocate(120000, [500000, 300000]) == [75000, 45000]


def test_allocate_gives_leftover_to_largest_remainder():
    # 10 centavos entre pesos 1 e 2: 3,33 e 6,66 -> sobra 1 centavo
    parts = allocate(10, [1, 2])
    assert sum(parts) == 10
    assert parts == [3, 7]  # o resto maior (0.66) leva o centavo


def test_allocate_zero_weights_splits_evenly():
    assert allocate(101, [0, 0]) == [51, 50]
    assert sum(allocate(101, [0, 0])) == 101


def test_allocate_handles_negative_total():
    parts = allocate(-100, [1, 1, 1])
    assert sum(parts) == -100
    assert parts == [-34, -33, -33]


def test_allocate_edge_cases():
    assert allocate(0, [1, 1]) == [0, 0]
    assert allocate(100, []) == []
    assert allocate(7, [1]) == [7]


@pytest.mark.parametrize("total", [1, 7, 99, 100, 12345, 199147_79, 1_000_000_01])
@pytest.mark.parametrize("weights", [[1, 1], [1, 2], [500000, 300000], [1, 1, 1, 1, 1, 1, 7]])
def test_allocate_always_conserves_the_total(total, weights):
    """A propriedade que importa: nenhum centavo aparece ou some, nunca."""
    parts = allocate(total, weights)
    assert sum(parts) == total
    assert len(parts) == len(weights)


def test_sum_of_real_data_is_exact():
    """Os mesmos valores que em float davam 199147.79000000018."""
    amounts = [1227519, 178259, 94431] * 625
    assert sum(amounts) == (1227519 + 178259 + 94431) * 625  # exato, sem epsilon
