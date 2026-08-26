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

## Migration stages

1. Separate the existing repository into independent uv projects without changing hardware/UI behaviour.
2. Extract shared state and parameter models from the legacy `domain.py` into `zhoutomo_protocol`.
3. Replace legacy top-level imports with `zhoutomo_server.*` and `zhoutomo_client.*` imports.
4. Split the FastAPI server into routers/services/state and the temscript implementation into driver modules.
5. Decouple autofocus/autotilt workflow logic from Qt controllers.
6. Add simulator-backed integration tests before changing external API behaviour.

During stage 1, several legacy modules keep their historical top-level import names inside the individual uv project. Compatibility shims make those imports resolve locally; they are intentionally not cross-project dependencies.
