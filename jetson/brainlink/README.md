# rover-brainlink

One-way SSH tunnel from the rover to Gemma on the home Mac mini (`macmini/ai.rover.brain.plist`).
The rover is the client; the Mac mini's `authorized_keys` line for this key allows only a forward to
its `127.0.0.1:8080` (Gemma) and `127.0.0.1:8093` (Supertonic voice) (no commands, no reverse forwards). Why and how it was tested: `docs/preflight.md`
(2026-11-07, Gemma on the home Mac mini).

Key and pinned host key live on the Jetson in `/home/paulcho/brainlink/` (not in the repository).

```
docker build -t rover/brainlink:2 jetson/brainlink        # on the Jetson, from a copy of this folder
docker network create rover                                # once
docker run -d --name rover-brainlink --network rover -e MINI=192.168.1.197 \
  -v /home/paulcho/brainlink:/keys:ro -p 127.0.0.1:8080:8080 -p 127.0.0.1:8097:8093 \
  -p 127.0.0.1:8098:8098 rover/brainlink:3
docker network connect rover rover-control                 # the console reaches it as rover-brainlink:8080
```

On the Jetson host Gemma answers at `127.0.0.1:8080` as before and the Mac mini voice at `127.0.0.1:8097`
(the Jetson's own Supertonic stays on 8093 as the fallback). `MINI` is an address because
`.local` names do not resolve inside containers; the Mac mini is on DHCP and WiFi.
