# ZhouTomo

ZhouTomo is an automated electron-microscope control and tomography application.

The repository is being migrated to a three-project monorepo:

- `server/`: Windows microscope-control service and hardware adapters.
- `client/`: PyQt GUI, acquisition workflows, and image-processing code.
- `protocol/`: platform-independent models and API contracts shared by both sides.

Each runtime project is managed independently with `uv`; the repository root is only the Git monorepo and is not a uv workspace.

## Development

```powershell
cd server
uv sync
uv run zhoutomo-server --mode null
```

```powershell
cd client
uv sync
uv run zhoutomo-client
```

The `temscript` dependency is optional and is only required on the Windows microscope-control machine:

```powershell
cd server
uv sync --extra hardware
```

See `docs/architecture.md` for the migration architecture and dependency rules.
