# ZhouTomo architecture

## Target dependency direction

```text
Client UI / workflows
        |
        v
Client API  ----->  zhoutomo-protocol  <-----  Server API
                                             |
                                             v
                                          Services
                                             |
                                             v
                                           Safety
                                             |
                                             v
                                          Drivers
                                             |
                                             v
                                      Microscope SDK
```

`protocol` is platform independent and must not import Qt, FastAPI, temscript, COM, or vendor SDKs.

`server` owns authoritative hardware state, hardware validation, safety checks, and vendor integrations.

`client` owns the desktop UI, high-level acquisition workflows, and image processing.

## Current migration status

### Completed

1. The repository root is now a Git monorepo rather than a Python environment.
2. `server`, `client`, and `protocol` are independent uv-managed Python projects.
3. Shared microscope state/parameter models were extracted into `zhoutomo_protocol`.
4. Stable package namespaces now exist for `zhoutomo_client.api/ui/workflows/processing` and `zhoutomo_server.api/drivers/state/wiring`.
5. Generated logs, build output, IDE state, and VSCodeCounter output were removed from the source tree and ignored.
6. Windows CI verifies all three projects without requiring microscope hardware.

### Transitional compatibility layer

The implementation-heavy legacy packages (`view`, `autofocus`, `autotilt`, `src`) are currently installed only inside the client project. The legacy server modules (`server_fastapi`, `ports_temscript`, `wiring`, `run_agent`) are installed only inside the server project. Stable `zhoutomo_*` modules wrap these implementations while imports are migrated incrementally.

This is deliberate: moving every file and rewriting every import in a single commit would combine packaging changes with behavioural changes and make hardware regressions difficult to isolate.

## Next migration stages

1. Replace internal legacy imports with `zhoutomo_server.*`, `zhoutomo_client.*`, and `zhoutomo_protocol.*` imports.
2. Split the FastAPI server into routers, services, and runtime state.
3. Split the temscript implementation into stage/camera/optics/microscope adapters behind explicit driver protocols.
4. Move server-authoritative range checks and interlocks into `zhoutomo_server.safety`.
5. Decouple autofocus/autotilt workflow logic from Qt controllers so workflows can run headlessly.
6. Add simulator-backed client/server integration tests before changing external API behaviour.
