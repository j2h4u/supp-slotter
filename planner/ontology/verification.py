"""Weak identity registry for verified ontology bundle provenance."""

from __future__ import annotations

import threading
import weakref

_REGISTERED_BUNDLES: dict[int, weakref.ReferenceType[object]] = {}
_REGISTERED_BUNDLES_LOCK = threading.Lock()


def register_bundle(bundle: object) -> object:
    """Register one live bundle after its artifact contract has been proven."""

    identity = id(bundle)

    def discard(reference: weakref.ReferenceType[object]) -> None:
        with _REGISTERED_BUNDLES_LOCK:
            if _REGISTERED_BUNDLES.get(identity) is reference:
                del _REGISTERED_BUNDLES[identity]

    reference = weakref.ref(bundle, discard)
    with _REGISTERED_BUNDLES_LOCK:
        _REGISTERED_BUNDLES[identity] = reference
    return bundle


def is_registered_bundle(value: object) -> bool:
    """Return whether this exact live object was registered as verified."""

    with _REGISTERED_BUNDLES_LOCK:
        reference = _REGISTERED_BUNDLES.get(id(value))
        return reference is not None and reference() is value
