# Performance Notes

Paktool keeps its command surface (`unpack`, `repack`, and `inject`) while reducing avoidable Termux overhead. These timings are a reproducible smoke fixture using a lightweight fake `repak` backend; real PAK timing depends primarily on PAK size, compression, phone storage speed, and the UE4 version.

| Path | Verified smoke timing | Bottleneck and behavior |
|---|---:|---|
| Cached background update | 0.001 s | A successful update check now suppresses further checks for six hours, so `paktool` does not repeatedly start network/Git work. |
| Startup/help | 0.086 s | Python process startup and argument parsing. Interactive launches keep Git work detached. |
| Unpack | 0.119 s | The external `repak unpack` process does the actual archive work. |
| Repack | 0.115 s | The external `repak pack` process does the actual archive work. |
| Lua inject | 0.139 s | Inject must unpack a source PAK, copy Lua files into temporary staging, and pack a new PAK. |

For directory injection, Paktool now streams matching `*.lua` files instead of constructing and sorting a complete file list, and uses content-only file copies because PAK assembly does not need source timestamp metadata.

## Device controls

The default update interval is six hours after a successful background check. Advanced users can change it for their own device:

```bash
PAKTOOL_UPDATE_INTERVAL_SECONDS=43200 paktool
```

To skip one background update check while troubleshooting:

```bash
PAKTOOL_NO_UPDATE=1 paktool
```

Paktool injection cannot be made equivalent to a simple copy operation because it must create a valid new PAK. The most meaningful real-device speed improvement is to use fast local storage, inject only the required Lua files, and avoid optional compression unless the project requires it.
