"""The H10 method digest in force: the one Eleonora registered on #23 (#200, step 5; constants set by #202).

**This file is not part of the method digest** (`h10_live.METHOD_FILES`), on purpose: a registered digest that lived in a file
the digest covers could never equal it (the constant would change the digest it names). Her registration of a new method
updates `REGISTERED_DIGEST` here, in the pull request that follows her comment on #23; nothing else does.

`h10_live.attribute_onset` refuses to produce a row whose `method_digest` is not `REGISTERED_DIGEST`. Since her registration of
3 November 2026 the constants name the code at `REGISTERED_COMMIT` with the parent at `REGISTERED_PARENT`, and this tree's
method digest is the registered one while no covered file changes. A later change to a covered file, or a parent checkout other
than the pin, changes the digest and the entry point refuses until a new registration updates the constants. Standard library only.
"""

#: H10's registration of 3 November 2026 on #23 (Eleonora's own comment,
#: https://github.com/eleonorabjornberg/repo-market-liquidity/issues/23#issuecomment-6618862828; the page is
#: docs/research/h10-reregistration-2.md): the method digest, the commit of this repository it was made at (#201's merge),
#: and the parent pin it names. Set by #202, the follow-up pull request her registration names.
REGISTERED_DIGEST = "54b5f151c757b1cff5d3ebe6e8ce202bd41cafc4d8104effb00f3da4617c8770"
REGISTERED_COMMIT = "ba1860cb096b3c7f92a6975e6908be7a480e459c"
REGISTERED_PARENT = "2032de4a7d7802289bc5a78dfc02599752bc7c5c"


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
