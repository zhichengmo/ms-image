"""Legacy replay namespace retained only to make removal explicit.

The former ``xray_accuracy_worker`` replay implementation was removed with
the legacy XRay runtime.  Keeping this marker avoids an import-time reference
to a deleted worker while preventing callers from mistaking replay tooling
for a supported Runtime execution path.
"""

__all__: tuple[str, ...] = ()
