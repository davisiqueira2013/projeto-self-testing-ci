import pytest
from wallet.gateways.kyc import CpfKycProvider

from tests.support import make_cpf
from wallet.domain.rules import is_valid_cpf, normalize_document


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", "111.444.777-35"])
def test_valid_cpfs(cpf):
    assert is_valid_cpf(cpf) is True


@pytest.mark.parametrize(
    "cpf",
    [
        "529.982.247-26",  # segundo dígito errado
        "529.982.247-15",  # primeiro dígito errado
        "111.111.111-11",  # todos iguais
        "1234567890",  # tamanho inválido
        "",
        None,
    ],
)
def test_invalid_cpfs(cpf):
    assert is_valid_cpf(cpf) is False


def test_normalize_document_keeps_only_digits():
    assert normalize_document(" 529.982.247-25 ") == "52998224725"


@pytest.mark.parametrize("seed", range(20))
def test_cpf_generator_used_by_tests_produces_valid_documents(seed):
    assert is_valid_cpf(make_cpf(seed))


class TestCpfKycProvider:
    def test_approves_valid_holder(self):
        assert CpfKycProvider().validate("Ana Souza", "52998224725").approved is True

    def test_rejects_short_name(self):
        result = CpfKycProvider().validate(" Al ", "52998224725")
        assert result.approved is False
        assert "name" in result.reason

    def test_rejects_invalid_cpf(self):
        result = CpfKycProvider().validate("Ana Souza", "12345678900")
        assert (result.approved, result.reason) == (False, "invalid CPF")
