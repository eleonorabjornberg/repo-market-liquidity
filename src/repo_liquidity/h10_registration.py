"""The H10 method digest in force: the one Eleonora registered on #23 (#200, step 5).

**This file is not part of the method digest** (`h10_live.METHOD_FILES`), on purpose: a registered digest that lived in a file
the digest covers could never equal it (the constant would change the digest it names). Her registration of a new method
updates `REGISTERED_DIGEST` here, in the pull request that follows her comment on #23; nothing else does.

`h10_live.attribute_onset` refuses to produce a row whose `method_digest` is not `REGISTERED_DIGEST`. Between the merge of the
pin move (#200) and her new registration, `main` carries code whose digest is not the registered one, so the entry point
refuses on `main`, and a live H10 run must use the registered code: this repository at `REGISTERED_COMMIT` with the parent at
`REGISTERED_PARENT`, which together give `REGISTERED_DIGEST`. Standard library only.
"""

#: H10's registration of 22 October 2026 on #23 (docs/research/h10-reregistration.md): the method digest, the commit of this
#: repository it was made at, and the parent pin it names.
REGISTERED_DIGEST = "43bf1303164c3c085b33ccf762268b721a5bddc9d7a4dcf68524c67ea33d15bb"
REGISTERED_COMMIT = "7838483"
REGISTERED_PARENT = "08ff67e27bc3d7e357491cf8e1da59793702b3fb"


def check_registered(digest: str, registered: str = REGISTERED_DIGEST) -> None:
    """Raise ValueError unless `digest` is the registered method digest.

    Raises:
        ValueError: `digest` is not `registered`; the message names both and where the registered code is.
    """
    if digest != registered:
        raise ValueError(
            f"this code's H10 method digest {digest} is not the registered {registered}; a live H10 row is made only by the "
            f"registered code (repo-market-liquidity at {REGISTERED_COMMIT} with the parent at {REGISTERED_PARENT}) until a "
            "new registration on #23 updates repo_liquidity.h10_registration")
