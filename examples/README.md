# Examples

## Standalone Config

Use `examples/unigate.json` as a starting point for standalone use. Copy it
into another project if needed and adjust the storage path, prefix, host, port,
and declared instances.

Validate it:

```powershell
unigate check-config --config .\examples\unigate.json
```

Print the resolved summary:

```powershell
unigate print-config --config .\examples\unigate.json
```

Serve it with optional extras installed:

```powershell
pip install -e .[server]
unigate serve --config .\examples\unigate.json
```

## Embedded Use

Another project can keep its own config file elsewhere and still use the same
runtime:

```python
from unigate import build_gate_from_config, create_asgi_app

gate, config = build_gate_from_config("H:/my-project/unigate.json")
app = create_asgi_app(gate, prefix=config["unigate"].get("asgi_prefix", "/unigate"))
```
