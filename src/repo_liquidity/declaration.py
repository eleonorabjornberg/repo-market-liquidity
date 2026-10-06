"""Phase 3's declaration: the parent's registry and feature map, plus Phase 3's own entries.

`docs/decisions/input-declarations.md`: Phase 3's new inputs are declared and parsed in this repository, as an
overlay checked by the parent's own validators. Inputs the parent declares but keeps off are switched on here, never
in the parent. The swap follows the parent's `scarcity.measurement_declaration`: `contract.FEATURE_FIELDS` and
`contract.FEATURE_SOURCES` are replaced together for the duration of a `with` block and restored after it.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType
from typing import Dict, List, Mapping

from repo_liquidity import parent_root

OVERLAY_PATH = Path(__file__).resolve().parents[2] / "metadata" / "sources_phase3.json"


def _parent_contract():
    from repo_model import contract

    return contract


#: Phase 3's columns and the (source, field) pairs each reads. The first three switch on inputs the parent declares
#: and keeps off; the rest read this repository's new sources.
def _fields():
    contract = _parent_contract()
    return {
        "on_rrp": tuple(contract.ON_RRP_OPERATION_RESULTS_FIELDS),
        "bank_total_assets": tuple(contract.BANK_TOTAL_ASSETS_FIELDS),
        "srf_take_up": tuple(contract.SRF_OPERATION_RESULTS_FIELDS),
        "soma_treasury_weekly_change": (("frb_h41_treasury", "soma_treasury_weekly_change"),),
        "srf_rate": (("fed_srf_rate", "srf_rate"),),
        "on_rrp_rate": (("fed_on_rrp_rate", "on_rrp_rate"),),
        "runoff_cap_treasury_bn": (("fomc_runoff_caps", "runoff_cap_treasury_bn"),),
        "runoff_cap_mbs_bn": (("fomc_runoff_caps", "runoff_cap_mbs_bn"),),
        "soma_mbs_weekly_change": (("frb_h41_mbs", "soma_mbs_weekly_change"),),
        "temp_repo_take_up": (("nyfed_temp_repo", "temp_repo_take_up"),),
        "temp_repo_term_take_up": (("nyfed_temp_repo", "temp_repo_term_take_up"),),
        "temp_repo_term_outstanding": (("nyfed_temp_repo", "temp_repo_term_outstanding"),),
        # Derived on each row from the two facilities' take-up, so read under both sources' declarations.
        "fed_repo_take_up": (("nyfed_temp_repo", "temp_repo_take_up"), ("nyfed_temp_repo", "temp_repo_term_outstanding"))
        + tuple(contract.SRF_OPERATION_RESULTS_FIELDS),
        "fed_repo_facility": (("nyfed_temp_repo", "temp_repo_take_up"),) + tuple(contract.SRF_OPERATION_RESULTS_FIELDS),
        "srf_material_use": tuple(contract.SRF_OPERATION_RESULTS_FIELDS),
        "fed_repo_material_use": (("nyfed_temp_repo", "temp_repo_take_up"), ("nyfed_temp_repo", "temp_repo_term_take_up"))
        + tuple(contract.SRF_OPERATION_RESULTS_FIELDS),
        # Stage 1b: fields of a source the parent declares, switched on here (`docs/stages/stage-1b.md`). `effr` is
        # already in the parent's feature map (`nyfed_effr`); only the build reads it.
        "sofr_p1": (("nyfed_sofr", "SOFR_p1"),),
        "sofr_p99": (("nyfed_sofr", "SOFR_p99"),),
    }


def _indicator_fields(fields):
    """Each Stage 1b indicator read under the declarations of the columns it is computed from."""
    from repo_liquidity import indicators

    contract = _parent_contract()
    known = {**contract.FEATURE_FIELDS, **fields}
    return {name: tuple(pair for column in inputs for pair in known[column])
            for name, inputs in indicators.INPUTS.items()}


FIELDS: Mapping[str, tuple] = MappingProxyType({**_fields(), **_indicator_fields(_fields())})

#: The columns the panel build prices from snapshots; the rest are scheduled and written on rows afterwards.
BUILT_COLUMNS = ("on_rrp", "bank_total_assets", "srf_take_up", "soma_treasury_weekly_change")
SCHEDULED_COLUMNS = ("srf_rate", "on_rrp_rate", "runoff_cap_treasury_bn", "runoff_cap_mbs_bn")
#: The Stage 1a correction's panel (version 2, `docs/stages/stage-1a-correction.md`): its added built columns, and the
#: columns derived on each row from columns already read at that row's decision instant (`repo_liquidity.fed_repo`).
BUILT_COLUMNS_V2 = BUILT_COLUMNS + ("soma_mbs_weekly_change", "temp_repo_take_up", "temp_repo_term_take_up",
                                    "temp_repo_term_outstanding")
DERIVED_COLUMNS_V2 = ("fed_repo_take_up", "fed_repo_facility", "srf_material_use", "fed_repo_material_use")
#: Stage 1b's panel (version 3, `docs/stages/stage-1b.md`): the parent inputs it switches on, then its indicators
#: (`repo_liquidity.indicators.COLUMNS`), derived on each row.
BUILT_COLUMNS_V3 = BUILT_COLUMNS_V2 + ("sofr_p1", "sofr_p99", "effr")


def parent_registry() -> Dict[str, Mapping]:
    return json.loads((parent_root() / "metadata" / "sources.json").read_text(encoding="utf-8"))


def overlay() -> Dict[str, Mapping]:
    return json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))


def merge(parent: Mapping[str, Mapping], extra: Mapping[str, Mapping]) -> Dict[str, Mapping]:
    """The parent's registry plus `extra`.

    Raises:
        ValueError: if an id in `extra` is already a parent source.
    """
    clash = sorted(set(parent) & set(extra))
    if clash:
        raise ValueError(f"overlay ids already declared by the parent: {clash}")
    return {**parent, **extra}


def registry() -> Dict[str, Mapping]:
    """The registry every Phase 3 build and read uses."""
    return merge(parent_registry(), overlay())


def validate(extra: Mapping[str, Mapping] = None) -> List[str]:
    """Problems the parent's validators find in the overlay; empty when it is sound."""
    from repo_model import asof, contract, registry as parent_registry_module

    extra = overlay() if extra is None else extra
    problems: List[str] = []
    for source_id, source in extra.items():
        problems += contract.validate_release_lag(source_id, source.get("release_lag"))
        if "scheduled_availability" in source:
            problems += asof.validate_scheduled_availability(source_id, source["scheduled_availability"])
    try:
        parent_registry_module.check_availability_provenance(extra)
    except ValueError as error:
        problems.append(str(error))
    return problems


@contextmanager
def phase3_declaration():
    """Phase 3's features switched on in the parent's feature map, for the duration of the block."""
    contract = _parent_contract()
    fields = MappingProxyType({**contract.FEATURE_FIELDS, **FIELDS})
    saved = contract.FEATURE_FIELDS, contract.FEATURE_SOURCES
    contract.FEATURE_FIELDS = fields
    contract.FEATURE_SOURCES = MappingProxyType(
        {feature: tuple(sorted({source for source, _field in pairs})) for feature, pairs in fields.items()}
    )
    try:
        yield
    finally:
        contract.FEATURE_FIELDS, contract.FEATURE_SOURCES = saved
