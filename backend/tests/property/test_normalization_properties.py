"""Property tests for skill normalization idempotence (design.md §5.1, R3.2)."""

from hypothesis import given
from hypothesis import strategies as st

from app.services.matching import normalize_skill
from app.services.matching.normalization import EDGE_PUNCTUATION
from app.services.matching.skill_catalog import ALIASES, CATALOG

_KNOWN_NAMES = sorted({*CATALOG, *ALIASES, *CATALOG.values()})
_EDGE = st.text(alphabet=EDGE_PUNCTUATION + " \t\n.\u3000\u00a0", max_size=6)


@st.composite
def _wrapped_known_name(draw: st.DrawFn) -> str:
    name = draw(st.sampled_from(_KNOWN_NAMES))
    upper = draw(st.booleans())
    return draw(_EDGE) + (name.upper() if upper else name) + draw(_EDGE)


@given(st.text(max_size=60))
def test_p_normalize_skill_is_idempotent_for_arbitrary_text(raw: str) -> None:
    """R3.2: normalizing an already-normalized skill changes nothing.

    **Validates: Requirements 3.2**
    """
    once = normalize_skill(raw)

    assert normalize_skill(once or "") == once


@given(_wrapped_known_name())
def test_p_normalize_skill_is_idempotent_for_wrapped_catalog_names(raw: str) -> None:
    """R1.3, R3.2: catalog/alias names wrapped in edge punctuation normalize to a fixed point.

    **Validates: Requirements 1.3, 3.2**
    """
    once = normalize_skill(raw)

    assert once is not None
    assert normalize_skill(once) == once
