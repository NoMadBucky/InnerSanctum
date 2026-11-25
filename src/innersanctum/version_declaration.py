"""Declare OKF 0.3 on a reviewed bundle without rewriting its index body."""

from collections import Counter
from datetime import datetime
from pathlib import Path
import re

from . import handover, migration, timestamp_cleanup, writer
from .schema import Refused, document, read_text, same


DECLARATION = 'okf_version: "0.3"'
ACTION = "OKF version declaration"


def updated_index(original):
    before, body, offset = document(original, required=False)
    newline = writer.lines_for(original)[1]
    if "okf_version" in before:
        raise Refused("The root index already declares a version; this cutover only adds a missing declaration.")
    if offset:
        opening, remaining = original.split("\n", 1)
        updated = opening + "\n" + DECLARATION + newline + remaining
    else:
        updated = newline.join(("---", DECLARATION, "---", "", "")) + original
    after, new_body, _ = document(updated)
    if not same(after, {**before, "okf_version": "0.3"}) or new_body != ("" if offset else newline) + body:
        raise Refused("The version declaration would change unrelated index content.")
    return updated


def audit_update(original, actor, when):
    return writer.edit_log(original, "index.md", "Declared OKF 0.3", actor, when, action=ACTION)


def describe(index, audit_before):
    result = {"status": "preview", "okf_version": "0.3", "index_before": index.before,
              "index_after": index.revision, "audit_before": audit_before}
    return {**result, "digest": writer.digest(writer.json_bytes(result))}


def plan(root):
    writer.require_idle(root)
    originals = [read_text(writer.read_file(writer.safe_target(root, name))) for name in ("index.md", "log.md")]
    index = writer.Change("index.md", writer.digest(originals[0].encode()), updated_index(originals[0]))
    return describe(index, writer.digest(originals[1].encode())), index, originals


def preview(root, successor=None):
    writer.check_authority(root, successor)
    return plan(root)[0]


def request_for(expected, actor, request_id, checkpoint_sha256=None):
    if type(expected) is not str or not writer.REVISION.fullmatch(expected):
        raise Refused("Provide the reviewed version preview digest.")
    writer.validate_actor(actor)
    request = writer.write_request(request_id, writer.VERSION_OPERATION, expected, actor,
                                   *(() if checkpoint_sha256 is None else (checkpoint_sha256,)))
    if request is None:
        raise Refused("The version declaration requires a durable request ID.")
    return request


def verify_changes(changes, originals, actor, expected, request, checkpoint_sha256=None):
    if ([c.path for c in changes] != ["index.md", "log.md"] or type(originals) is not list or len(originals) != 2
            or any(c.before != writer.digest(text.encode()) or c.after is None
                   for c, text in zip(changes, originals))):
        raise Refused("Invalid pending version declaration.")
    index, audit = changes
    if (index.after != updated_index(originals[0]) or describe(index, audit.before)["digest"] != expected
            or request != request_for(expected, actor, request[0], checkpoint_sha256)):
        raise Refused("The frozen version declaration differs from the reviewed preview.")
    added = (Counter(audit.after.splitlines()) - Counter(originals[1].splitlines())).elements()
    pattern = r"^\* \*\*" + re.escape(ACTION) + r"\*\* \(([^)]+)\) — "
    times = [m[1] for line in added if (m := re.match(pattern, line))]
    try:
        if len(times) != 1:
            raise ValueError
        when = datetime.fromisoformat(times[0])
    except ValueError:
        raise Refused("Invalid pending version audit timestamp.") from None
    if when.utcoffset() is None or audit.after != audit_update(originals[1], actor, when):
        raise Refused("The frozen version declaration changed unrelated audit text.")


def rehearse(root, expected, actor, request_id):
    return _apply(root, expected, actor, request_id)


def apply(root, expected, actor, request_id, *, successor, checkpoint, checkpoint_sha256, writers_stopped):
    if successor is None:
        raise Refused("Stopped-checkpoint version declaration requires the adopted checkout.")
    migration.require_stopped(root, checkpoint, checkpoint_sha256, writers_stopped)
    return _apply(root, expected, actor, request_id, successor=successor, checkpoint=checkpoint,
                  checkpoint_sha256=checkpoint_sha256)


def _apply(root, expected, actor, request_id, *, successor=None, checkpoint=None, checkpoint_sha256=None):
    writer.check_authority(root, successor)
    operation = writer.VERSION_OPERATION
    request = request_for(expected, actor, request_id, checkpoint_sha256)
    with writer.locked(root, successor) as state:
        writer.require_idle(root)
        if (receipt := writer.replay(root, state, request)) is not None:
            return receipt
        if successor is not None:
            snapshot, _ = migration.verified_checkpoint(root, successor, checkpoint, checkpoint_sha256)
            handover.compare_checkpoint(root, snapshot)
        result, index, originals = plan(root)
        if result["digest"] != expected:
            raise Refused("The version declaration preview changed; review a fresh preview.")
        formats = timestamp_cleanup.preview(root, successor)
        if formats["records"] or formats["blockers"]:
            raise Refused("Resolve outstanding timestamp cleanup before declaring OKF 0.3.")
        audit = audit_update(originals[1], actor, datetime.now().astimezone())
        changes = [index, writer.Change("log.md", result["audit_before"], audit)]
        for change in changes:
            read_text(change.after.encode())
        verify_changes(changes, originals, actor, expected, request, checkpoint_sha256)
        review = {"actor": actor, "digest": expected, "originals": originals}
        if successor is not None:
            review["checkpoint_sha256"] = checkpoint_sha256
        writer.freeze(root, state, changes, operation=operation, request=request, version_review=review)
        return writer.publish(root, state, changes, operation=operation, request=request,
                              successor=successor, maintenance=successor is not None)


def recover(root, expected, actor, request_id, *, successor, checkpoint, checkpoint_sha256, writers_stopped):
    if successor is None:
        raise Refused("Stopped-checkpoint version recovery requires the adopted checkout.")
    writer.check_authority(root, successor)
    migration.require_stopped(root, checkpoint, checkpoint_sha256, writers_stopped)
    request = request_for(expected, actor, request_id, checkpoint_sha256)
    with writer.locked(root, successor) as state:
        changes, operation, _, _, saved, _, _ = writer.read_changes(root, state)
        if operation != writer.VERSION_OPERATION or saved != request:
            raise Refused("Recovery requires the original version declaration request.")
        snapshot, _ = migration.verified_checkpoint(root, successor, checkpoint, checkpoint_sha256)
        result, index, _ = plan(Path(checkpoint).expanduser().absolute())
        if result["digest"] != expected or changes[0] != index:
            raise Refused("The pending version declaration differs from the checkpoint preview.")
        migration.check_recovery_snapshot(root, state, changes, snapshot, request)
        return writer.publish(root, state, changes, recovering=True, operation=operation, request=request,
                              successor=successor, maintenance=True)
