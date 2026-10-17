"""Money pattern: todo valor monetário do app é um `int` de centavos.

Por que
-------
`float` não representa 0,01 exatamente. Somar 1.875 transações em float já
acumulava erro real neste app (199147.79000000018 em vez de 199147.79), até
então mascarado por um `round()` na saída. Com `int` de centavos, soma e
subtração são exatas por construção — não existe erro para mascarar.

Regras
------
- Dinheiro é `Cents` (int). Nunca `float`, em lugar nenhum: banco, lógica, API.
- Conversão acontece só nas bordas: parsers de extrato (texto -> centavos) e
  exibição (centavos -> texto). No meio, é sempre int.
- Divisão de dinheiro usa `allocate()`, que conserva a soma. Multiplicar por uma
  proporção e arredondar cada parte isoladamente perde ou cria centavos.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Um valor monetário, em centavos. Alias de int — é só documentação de intenção.
Cents = int

_CENT = Decimal("0.01")


def from_decimal(value: Decimal) -> Cents:
    """Decimal em reais -> centavos, com arredondamento meio-para-cima.

    ROUND_HALF_UP (e não o bankers' rounding padrão do Python) porque é o que
    corresponde à expectativa de quem confere conta: 0,005 vira 0,01.
    """
    return int((value / _CENT).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_float(value: float) -> Cents:
    """Float -> centavos. Use SÓ em bordas legadas (migração de dados antigos).

    Passa por `str()` de propósito: `Decimal(0.1)` carrega o lixo binário do
    float, enquanto `Decimal(str(0.1))` dá exatamente 0.1.
    """
    return from_decimal(Decimal(str(value)))


def parse_brl(text: str) -> Cents | None:
    """Texto de extrato/planilha -> centavos. `None` se não for um número.

    Aceita os formatos que aparecem nos arquivos importados: "R$ 1.234,56"
    (PT-BR), "1,234.56" (US) e "1234.56". O sinal é preservado.
    """
    if text is None:
        return None
    cleaned = str(text).strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
    if not cleaned:
        return None

    negative = cleaned.startswith("-")
    cleaned = cleaned.lstrip("+-")

    # Decide qual separador é o decimal pelo que aparece por último.
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")  # PT-BR
        else:
            cleaned = cleaned.replace(",", "")  # US
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        # Só ponto: ambíguo. "1.000" é mil reais num extrato PT-BR (um real
        # seria "1,00"), mas "1234.56" é decimal. Grupo final de exatamente 3
        # dígitos, ou mais de um ponto, indica separador de milhar.
        head, _, tail = cleaned.rpartition(".")
        if "." in head or len(tail) == 3:
            cleaned = cleaned.replace(".", "")

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    cents = from_decimal(value)
    return -cents if negative else cents


def to_decimal(cents: Cents) -> Decimal:
    """Centavos -> Decimal em reais. Para exibir/exportar, não para calcular."""
    return (Decimal(cents) * _CENT).quantize(_CENT)


def format_brl(cents: Cents) -> str:
    """Centavos -> "R$ 1.234,56". Usado em logs e mensagens do backend."""
    negative = cents < 0
    reais, centavos = divmod(abs(cents), 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{'-' if negative else ''}R$ {inteiro},{centavos:02d}"


def allocate(total: Cents, weights: list[int]) -> list[Cents]:
    """Divide `total` centavos entre `weights`, conservando a soma exata.

    Método do maior resto (Hamilton): cada parte fica com a divisão inteira, e
    os centavos que sobram vão para quem tem o maior resto. Garante
    `sum(allocate(t, w)) == t` sempre — é isso que impede o centavo perdido no
    rateio proporcional ao salário.

    Pesos zerados (ou lista toda zerada) caem numa divisão igualitária, que é a
    regra do app quando ninguém declarou renda.
    """
    if not weights:
        return []

    # Trabalha no positivo e devolve o sinal no fim, para o resto/divisão
    # inteira não depender do comportamento de piso do Python com negativos.
    sign = -1 if total < 0 else 1
    total = abs(total)

    weight_sum = sum(weights)
    if weight_sum <= 0:
        base, leftover = divmod(total, len(weights))
        return [sign * (base + (1 if i < leftover else 0)) for i in range(len(weights))]

    shares = []
    remainders = []
    for w in weights:
        scaled = total * w
        shares.append(scaled // weight_sum)
        remainders.append(scaled % weight_sum)

    leftover = total - sum(shares)
    # Maior resto primeiro; empate resolve pelo índice, para ser determinístico.
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for i in order[:leftover]:
        shares[i] += 1

    return [sign * s for s in shares]
